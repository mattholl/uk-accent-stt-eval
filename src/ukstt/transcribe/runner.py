"""Run a set of clips through a transcriber: retries, threads, resume and run state."""

import csv
import json
import math
import random
import re
import shutil
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from ukstt.audio import sha256_file
from ukstt.config import StudyConfig
from ukstt.constants import CREDITS_PER_MIN, MAX_WORKERS
from ukstt.csvio import fmt_float
from ukstt.transcribe.base import (AuthOrQuotaError, ConnectError, HttpError, Transcriber, TranscribeError,
                                   validate_response, wire_params)

T = TypeVar("T")
LOG_COLUMNS = ("ts_utc", "clip_id", "backend", "status", "attempts", "http_status", "latency_s",
               "audio_seconds", "error")
RUN_ID_RE = r"[A-Za-z0-9_-]{1,64}"
MAX_RETRY_AFTER_S = 60.0
NORMALISE_CSV = Path("config/normalise.csv")


def _retry_after(exc: Exception) -> float:
    """The server's Retry-After in seconds, capped; 0 unless it is a finite number >= 0."""
    try:
        value = float(getattr(exc, "retry_after", None))
    except (TypeError, ValueError):
        return 0.0
    return min(value, MAX_RETRY_AFTER_S) if math.isfinite(value) and value >= 0 else 0.0


def call_with_retry(fn: Callable[[], T], *, max_retries: int, sleep: Callable[[float], None] = time.sleep) -> T:
    """Call fn; retry 429, 5xx and connect errors with exponential backoff and jitter."""
    for k in range(max_retries + 1):
        try:
            return fn()
        except (HttpError, ConnectError) as exc:
            if isinstance(exc, HttpError) and not (exc.status == 429 or exc.status >= 500):
                raise
            if k == max_retries:
                raise
            sleep(max(_retry_after(exc), min(30, 2 * 2**k) + random.random()))
    raise AssertionError("unreachable")


@dataclass(frozen=True)
class RunOptions:
    run_id: str
    backend: str
    max_audio_minutes: float | None
    workers: int
    force: bool
    clips_path: Path  # the clips file the rows came from: hashed and copied into the run directory


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def run_transcription(clips: list[dict[str, str]], opts: RunOptions, cfg: StudyConfig,
                      transcriber: Transcriber, sleep: Callable[[float], None] = time.sleep) -> int:
    """Returns the exit code: 0 ok, 2 usage/gate/validation, 4 some clips failed, 5 auth or quota."""
    def refuse(message: str) -> int:
        print(f"error: {message}", file=sys.stderr)
        return 2

    if not re.fullmatch(RUN_ID_RE, opts.run_id):
        return refuse("run id may only contain letters, digits, '_' and '-' (1-64 characters)")
    ids = [c["clip_id"] for c in clips]
    if len(set(ids)) != len(ids):
        return refuse("duplicate clip_id in the clips file")
    clips = sorted(clips, key=lambda c: c["clip_id"])
    run_dir = cfg.runs_dir / opts.run_id
    raw_dir = run_dir / "raw"
    wire = wire_params(cfg.params)
    clips_hash = sha256_file(opts.clips_path)
    manifest_path = run_dir / "run_manifest.json"

    todo = [c for c in clips if opts.force or not (raw_dir / f"{c['clip_id']}.json").exists()]
    seconds = {c["clip_id"]: float(c["duration_s"]) for c in clips}
    if opts.backend == "elevenlabs" and opts.max_audio_minutes is None:
        return refuse("--backend elevenlabs needs --max-audio-minutes N (the only spend guard)")
    if transcriber.name != opts.backend:
        return refuse(f"the transcriber is '{transcriber.name}' but --backend is '{opts.backend}'")
    if opts.max_audio_minutes is not None:
        if not 0 < opts.max_audio_minutes < math.inf:  # also false for nan
            return refuse("--max-audio-minutes must be a finite number above 0")
        total = sum(seconds[c["clip_id"]] for c in todo)
        if not total <= opts.max_audio_minutes * 60:
            return refuse(f"{total / 60:.2f} min of audio to send exceeds --max-audio-minutes {opts.max_audio_minutes}")
    for c in todo:
        if not Path(c["audio_path"]).is_file():
            return refuse(f"audio file not found: {c['audio_path']}")
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key, new in (("backend", opts.backend), ("params", wire), ("clips_file_sha256", clips_hash)):
            if old.get(key) != new:
                return refuse(f"{manifest_path} was made with a different {key}; use a new --run-id")

    send_min = sum(seconds[c["clip_id"]] for c in todo) / 60
    if opts.backend == "elevenlabs":
        print(f"to send: {len(todo)} clips, {send_min:.2f} min (about {send_min * CREDITS_PER_MIN:.0f} credits at "
              f"{CREDITS_PER_MIN} credits/min, unverified; check the dashboard)")
    else:
        print(f"to send (fake): {len(todo)} clips, {send_min:.2f} min")

    workers = max(1, min(opts.workers, MAX_WORKERS))
    raw_dir.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        _write_atomic(manifest_path, json.dumps({
            "run_id": opts.run_id,
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "backend": opts.backend,
            "params": wire,
            "clips_file_sha256": clips_hash,
            "normalise_csv_sha256": sha256_file(NORMALISE_CSV) if NORMALISE_CSV.is_file() else "",
        }, indent=2) + "\n")
    shutil.copyfile(opts.clips_path, run_dir / "clips.csv")

    log_path = run_dir / "transcribe_log.csv"
    lock = threading.Lock()
    stop = threading.Event()  # set by an auth/quota error: nothing further is submitted
    counts = {"ok": 0, "skipped": 0, "failed": 0}
    codes = {0}
    new_log = not log_path.exists() or log_path.stat().st_size == 0
    with open(log_path, "a", encoding="utf-8", newline="") as log_fh:
        writer = csv.writer(log_fh, lineterminator="\n")
        if new_log:
            writer.writerow(LOG_COLUMNS)

        def log(clip_id: str, status: str, attempts: int = 0, http: object = "", latency: float | None = None,
                error: str = "") -> None:
            with lock:
                counts[status] += 1
                writer.writerow([datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), clip_id, opts.backend,
                                 status, attempts, http, fmt_float(latency), fmt_float(seconds[clip_id]), error])
                log_fh.flush()

        def work(clip: dict[str, str]) -> None:
            clip_id = clip["clip_id"]
            raw_path = raw_dir / f"{clip_id}.json"
            if not opts.force and raw_path.exists():
                log(clip_id, "skipped")
                return
            if stop.is_set():
                return
            attempts = 0

            def attempt() -> dict:
                nonlocal attempts
                attempts += 1
                raw = transcriber.transcribe(Path(clip["audio_path"]), cfg.params)
                validate_response(raw)
                return raw

            start = time.monotonic()
            try:
                raw = call_with_retry(attempt, max_retries=cfg.max_retries, sleep=sleep)
            except (TranscribeError, OSError) as exc:
                http = exc.status if isinstance(exc, HttpError) else ""
                msg = " ".join(f"{type(exc).__name__}: {exc}".split())[:300]
                log(clip_id, "failed", attempts, http, time.monotonic() - start, msg)
                with lock:
                    codes.add(5 if isinstance(exc, AuthOrQuotaError) else 4)
                if isinstance(exc, AuthOrQuotaError):
                    stop.set()
                return
            _write_atomic(raw_path, json.dumps(raw, indent=2) + "\n")
            log(clip_id, "ok", attempts, 200 if opts.backend == "elevenlabs" else "", time.monotonic() - start)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            try:
                for future in [pool.submit(work, c) for c in clips]:
                    future.result()
            except BaseException:  # Ctrl-C: do not send the clips still queued
                stop.set()
                pool.shutdown(wait=True, cancel_futures=True)
                raise

    print(f"run {opts.run_id}: {counts['ok']} ok, {counts['skipped']} skipped, {counts['failed']} failed -> {run_dir}")
    return max(codes)
