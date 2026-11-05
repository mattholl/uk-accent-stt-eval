"""Command-line entry point for the UK/Irish accent STT benchmark."""

import argparse
import csv
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from ukstt import __version__
from ukstt.aggregate import score_run, stats_run
from ukstt.audio import sha256_file
from ukstt.config import DEFAULT_CONFIG, load_config
from ukstt.constants import SEED
from ukstt.csvio import read_csv
from ukstt.dummy import make_dummy_data
from ukstt.manifest import build_manifest, select_stage, total_minutes
from ukstt.transcribe.elevenlabs import ElevenLabsTranscriber, load_api_key
from ukstt.transcribe.fake import FakeTranscriber
from ukstt.transcribe.runner import NORMALISE_CSV, RUN_ID_RE, RunOptions, run_transcription

CLIPS_IN = Path("manifests/clips_in.csv")
DEMO_IN = Path("manifests/demo_in.csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ukstt", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, metavar="PATH",
                        help="study config (default %(default)s)")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("make-dummy-data", help="write synthetic clips and references")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--clips-per-region", type=int, default=4)
    p.add_argument("--speakers-per-region", type=int, default=2)
    p.add_argument("--seconds", type=float, default=20)
    p.add_argument("--seed", type=int, default=SEED)
    p.set_defaults(func=cmd_make_dummy_data)

    p = sub.add_parser("build-manifest", help="validate clips_in.csv files and write clips.csv")
    p.add_argument("--in", dest="inputs", type=Path, action="append", metavar="CSV",
                   help="input manifest, repeatable (default manifests/clips_in.csv plus manifests/demo_in.csv if present)")
    p.add_argument("--regions", type=Path, default=Path("config/regions.csv"))
    p.add_argument("--out", type=Path, default=Path("manifests/clips.csv"))
    p.add_argument("--report", type=Path, default=Path("manifests/validation_report.csv"))
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.set_defaults(func=cmd_build_manifest)

    p = sub.add_parser("select", help="pick the clips of one stage from clips.csv")
    p.add_argument("--clips", type=Path, default=Path("manifests/clips.csv"))
    p.add_argument("--stage", required=True, choices=("smoke", "pilot", "demo"))
    p.add_argument("--out", type=Path, help="default: <dir of clips.csv>/<stage>.csv")
    p.add_argument("--cap-minutes", type=float, help="pilot only: replace the 10-minute cap (finite, above 0)")
    p.set_defaults(func=cmd_select)

    p = sub.add_parser("transcribe", help="send the clips of a manifest to a speech-to-text backend")
    p.add_argument("--clips", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--backend", choices=("fake", "elevenlabs"), default="fake")
    p.add_argument("--max-audio-minutes", type=float, help="required for the real backend: refuse to send more audio")
    p.add_argument("--workers", type=int, help="parallel requests, at most 8 (default from the config)")
    p.add_argument("--force", action="store_true", help="send every clip again and overwrite the raw files")
    p.add_argument("--fake-config", type=Path, default=Path("config/fake.toml"))
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("score", help="score a run: utterance_scores, speaker_scores, error_pairs")
    p.add_argument("--run-id", required=True)
    p.add_argument("--clips", type=Path, help="default: the snapshot runs/<run_id>/clips.csv")
    p.add_argument("--out", type=Path, help="default: <results_dir>/<run_id>")
    p.add_argument("--accept-normalise-change", action="store_true",
                   help="score even though config/normalise.csv changed since the run, and record the new hash")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("stats", help="region_summary and pairwise_vs_baseline from a scored run")
    p.add_argument("--run-id", required=True)
    p.add_argument("--out", type=Path, help="default: <results_dir>/<run_id>")
    p.set_defaults(func=cmd_stats)
    return parser


def cmd_make_dummy_data(args: argparse.Namespace) -> int:
    make_dummy_data(args.out, args.clips_per_region, args.speakers_per_region, args.seconds, seed=args.seed)
    print(f"wrote dummy data to {args.out}")
    return 0


def cmd_build_manifest(args: argparse.Namespace) -> int:
    inputs = args.inputs or [CLIPS_IN] + ([DEMO_IN] if DEMO_IN.exists() else [])
    issues = build_manifest(inputs, args.regions, args.out, args.report, strict=args.strict)
    for i in issues:
        print(f"{i.level} {i.code} {i.path}: {i.message}", file=sys.stderr)
    errors = sum(i.level == "error" for i in issues)
    print(f"{errors} error(s), {len(issues) - errors} warning(s); report: {args.report}")
    if errors:
        return 2
    rows = read_csv(args.out)
    regions = {r["region"] for r in rows} - {"unknown"}
    print(f"{len(rows)} clips, {len(regions)} regions, "
          f"{len({r['speaker_id'] for r in rows})} speakers, {total_minutes(rows):.1f} min -> {args.out}")
    return 0


def cmd_select(args: argparse.Namespace) -> int:
    out = args.out or args.clips.parent / f"{args.stage}.csv"
    rows = select_stage(args.clips, args.stage, out, args.cap_minutes)
    print(f"{args.stage}: {len(rows)} clips, {total_minutes(rows):.2f} min -> {out}")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    clips = read_csv(args.clips)
    if not clips:
        raise ValueError(f"{args.clips} has no clips")
    workers = args.workers if args.workers is not None else cfg.default_workers
    if workers < 1:
        raise ValueError("--workers must be at least 1")
    if args.backend == "fake":
        transcriber = FakeTranscriber.from_clips(args.clips, args.fake_config)
    else:
        transcriber = ElevenLabsTranscriber(load_api_key(), cfg.connect_timeout_s, cfg.read_timeout_s)
    opts = RunOptions(args.run_id, args.backend, args.max_audio_minutes, workers, args.force, args.clips)
    return run_transcription(clips, opts, cfg, transcriber)


def _check_run_id(run_id: str) -> None:
    if not re.fullmatch(RUN_ID_RE, run_id):
        raise ValueError("run id may only contain letters, digits, '_' and '-' (1-64 characters)")


def cmd_score(args: argparse.Namespace) -> int:
    _check_run_id(args.run_id)
    cfg = load_config(args.config)
    run_dir = cfg.runs_dir / args.run_id
    out = args.out or cfg.results_dir / args.run_id
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = sha256_file(NORMALISE_CSV)
    changed = manifest.get("normalise_csv_sha256") != current
    if changed:
        if not args.accept_normalise_change:
            print(f"error: {NORMALISE_CSV} changed since run {args.run_id} was transcribed; "
                  "use --accept-normalise-change to score anyway", file=sys.stderr)
            return 2
        manifest["normalise_csv_sha256"] = current
    for stale in ("region_summary.csv", "pairwise_vs_baseline.csv"):  # they belong to the previous scoring
        (out / stale).unlink(missing_ok=True)
    score_run(run_dir, args.clips or run_dir / "clips.csv", out)
    if changed:  # only reached with --accept-normalise-change, and only after scoring succeeded
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    rows = read_csv(out / "utterance_scores.csv")
    print(f"scored {len(rows)} clips ({sum(r['status'] == 'ok' for r in rows)} ok) -> {out}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    _check_run_id(args.run_id)
    out = args.out or load_config(args.config).results_dir / args.run_id
    stats_run(out)
    print(f"wrote region_summary.csv and pairwise_vs_baseline.csv -> {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return func(args)
    except (OSError, ValueError, csv.Error, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
