"""Manifest validation (build-manifest) and stage selection (select)."""

import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ukstt.audio import probe_wav, sha256_file
from ukstt.constants import DEMO_CAP_MIN, ID_RE, PILOT_CAP_MIN, PILOT_REGIONS
from ukstt.csvio import fmt_float, read_csv, write_csv
from ukstt.normalise import normalise_default

IN_COLUMNS = ("clip_id", "set", "speaker_id", "region", "task", "audio_path", "reference_path", "source", "notes")
OUT_COLUMNS = IN_COLUMNS + ("audio_sha256", "duration_s", "sample_rate_hz", "channels")
REPORT_COLUMNS = ("level", "code", "path", "message")

MIN_SECONDS = 0.1
LONG_SECONDS = 60.0
SELECT_COLUMNS = ("clip_id", "set", "region", "duration_s")
FFMPEG_HINT = "convert with: ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav"
_BRACKET = re.compile(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>")


@dataclass(frozen=True)
class Issue:
    level: str  # error | warning
    code: str
    path: str
    message: str


def build_manifest(clips_in_csvs: Sequence[Path], regions_csv: Path, out_csv: Path, report_csv: Path,
                   strict: bool = False) -> list[Issue]:
    """Validate the inputs (concatenated in the order given) and write the report.

    clips.csv is written only when there is no error. With strict, warnings are
    reported as errors, so they block clips.csv too.
    """
    region_rows = read_csv(regions_csv)
    if not region_rows or "region_id" not in region_rows[0]:
        raise ValueError(f"{regions_csv}: needs a region_id column and at least one row")
    regions = {row["region_id"] for row in region_rows}
    clips: list[dict[str, str]] = []
    for csv_path in clips_in_csvs:
        rows = read_csv(csv_path)
        missing = [c for c in IN_COLUMNS if rows and c not in rows[0]]
        if missing:
            raise ValueError(f"{csv_path}: missing column(s): {', '.join(missing)}")
        clips.extend({c: row.get(c) or "" for c in IN_COLUMNS} for row in rows)
    if not clips:
        raise ValueError("the input file(s) hold no clip rows (empty file or header only)")

    issues: list[Issue] = []
    seen: set[str] = set()
    speaker_clips: dict[str, list[str]] = {}
    out_rows = []
    for row in clips:
        extra = _check_clip(row, regions, seen, issues)
        seen.add(row["clip_id"])
        if row["set"] != "demo":  # each demo clip is its own speaker by design
            speaker_clips.setdefault(row["speaker_id"], []).append(row["clip_id"])
        out_rows.append({**row, **extra})
    for speaker, ids in speaker_clips.items():
        if len(ids) == 1:
            issues.append(Issue("warning", "W_SINGLE_CLIP_SPEAKER", ids[0],
                                f"speaker {speaker!r} has only this clip"))
    if strict:
        issues = [replace(i, level="error") if i.level == "warning" else i for i in issues]

    write_csv(report_csv, (asdict(i) for i in issues), REPORT_COLUMNS)
    if any(i.level == "error" for i in issues):
        out_csv.unlink(missing_ok=True)  # never leave a stale clips.csv for select to use
    else:
        write_csv(out_csv, out_rows, OUT_COLUMNS)
    return issues


def _check_clip(row: dict[str, str], regions: set[str], seen: set[str], issues: list[Issue]) -> dict[str, str]:
    """Append this clip's issues; return the audio columns (empty if the audio is unusable)."""
    cid = row["clip_id"]

    def add(level: str, code: str, path: str, message: str) -> None:
        issues.append(Issue(level, code, path, message if path == cid else f"{cid}: {message}"))

    demo = row["set"] == "demo"
    for column in ("clip_id", "speaker_id"):
        if not re.fullmatch(ID_RE, row[column]):
            add("error", "E_ID_BAD", cid, f"{column} {row[column]!r} does not match {ID_RE}")
    if cid in seen:
        add("error", "E_DUP_CLIP", cid, "duplicate clip_id")
    if row["set"] not in ("pilot", "demo"):
        add("error", "E_SET_BAD", cid, f"set {row['set']!r} is not pilot or demo")
    if row["region"] == "unknown" and demo:
        pass
    elif row["region"] not in regions:
        add("error", "E_REGION_UNKNOWN", cid, f"region {row['region']!r} is not in the regions file"
            + ("" if demo else " (unknown is allowed for demo clips only)"))
    if row["task"] not in (("read", "spont", "unknown") if demo else ("read", "spont")):
        add("error", "E_TASK_BAD", cid, f"task {row['task']!r} is not allowed for this set")

    _check_reference(row, demo, add)
    return _check_audio(row["audio_path"], add)


def _check_reference(row: dict[str, str], demo: bool, add) -> None:
    ref = row["reference_path"]
    if not ref:
        if not demo:
            add("error", "E_REF_MISSING", ref, "reference_path is required for pilot clips")
        return
    if not Path(ref).is_file():
        add("error", "E_REF_MISSING", ref, "reference file not found")
        return
    text = Path(ref).read_text(encoding="utf-8-sig", errors="replace")
    if not normalise_default(text):
        add("error", "E_REF_EMPTY_AFTER_NORM", ref, "reference has no words after normalisation")
    if any(ch.isdigit() for ch in text):
        add("warning", "W_REF_DIGITS", ref, "reference contains digits (the normaliser spells them out)")
    if _BRACKET.search(text):
        add("warning", "W_REF_BRACKET", ref, "reference contains a bracketed span (removed by the normaliser)")


def _check_audio(audio: str, add) -> dict[str, str]:
    if not audio or not Path(audio).is_file():
        add("error", "E_AUDIO_MISSING", audio, "audio file not found")
        return {}
    try:
        info = probe_wav(Path(audio))
    except ValueError as exc:
        add("error", "E_AUDIO_FORMAT", audio, f"{exc}; {FFMPEG_HINT}")
        return {}
    if info.channels != 1 or info.sampwidth_bytes != 2 or info.sample_rate_hz < 16000:
        add("error", "E_AUDIO_FORMAT", audio,
            f"need PCM16 mono >=16 kHz, got {info.sampwidth_bytes * 8}-bit, {info.channels} channel(s), "
            f"{info.sample_rate_hz} Hz; {FFMPEG_HINT}")
        return {}
    if info.duration_s < MIN_SECONDS:
        add("error", "E_AUDIO_TOO_SHORT", audio, f"duration {info.duration_s:.3f} s is under {MIN_SECONDS} s")
        return {}
    if info.duration_s > LONG_SECONDS:
        add("warning", "W_DURATION", audio, f"duration {info.duration_s:.1f} s is over {LONG_SECONDS:.0f} s")
    return {"audio_sha256": sha256_file(Path(audio)), "duration_s": fmt_float(info.duration_s),
            "sample_rate_hz": str(info.sample_rate_hz), "channels": str(info.channels)}


def select_stage(clips_csv: Path, stage: str, out_csv: Path, cap_min: float | None = None) -> list[dict[str, str]]:
    """Rows for a stage, sorted by clip_id, written to out_csv. ValueError if the stage cannot run.

    cap_min replaces PILOT_CAP_MIN for the pilot stage only (finite and > 0).
    """
    if stage not in ("smoke", "pilot", "demo"):
        raise ValueError(f"unknown stage {stage!r} (smoke, pilot or demo)")
    if cap_min is not None:
        if stage != "pilot":
            raise ValueError("--cap-minutes applies to --stage pilot only")
        if not 0 < cap_min < math.inf:  # also false for nan
            raise ValueError("--cap-minutes must be a finite number above 0")
    rows = sorted(read_csv(clips_csv), key=lambda r: r["clip_id"])
    missing = [c for c in SELECT_COLUMNS if rows and c not in rows[0]]
    if missing:
        raise ValueError(f"{clips_csv}: not a clips.csv from build-manifest (missing column(s): {', '.join(missing)})")
    if stage == "demo":
        chosen = [r for r in rows if r["set"] == "demo"]
        if not chosen:
            raise ValueError("no demo clips in the manifest")
        _check_cap(chosen, "demo", DEMO_CAP_MIN)
    else:
        pilot = [r for r in rows if r["set"] == "pilot" and r["region"] in PILOT_REGIONS]
        if stage == "smoke":
            chosen = [r for r in pilot if r["region"] == "southern"][:1]
            if not chosen:
                raise ValueError("no southern pilot clip for the smoke test")
        else:
            empty = [r for r in PILOT_REGIONS if not any(c["region"] == r for c in pilot)]
            if empty:
                raise ValueError(f"pilot region(s) with no clips: {', '.join(empty)}")
            _check_cap(pilot, "pilot", PILOT_CAP_MIN if cap_min is None else cap_min,
                       "; raise it with --cap-minutes X" if cap_min is None else "")
            chosen = pilot
    write_csv(out_csv, chosen, list(chosen[0]))
    return chosen


def _check_cap(rows: list[dict[str, str]], name: str, cap_min: float, hint: str = "") -> None:
    minutes = total_minutes(rows)
    if minutes > cap_min:
        raise ValueError(f"{name} set is {minutes:.2f} min, over the {cap_min} min cap{hint}")


def total_minutes(rows: Sequence[dict[str, str]]) -> float:
    return sum(float(r["duration_s"]) for r in rows) / 60
