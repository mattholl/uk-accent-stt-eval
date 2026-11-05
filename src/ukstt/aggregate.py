"""Turn a transcription run into the result tables (plan sections 7, 8 and 10)."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from ukstt.constants import BASELINE, MIN_SPEAKERS_CI, PILOT_REGIONS
from ukstt.csvio import fmt_float, read_csv, write_csv
from ukstt.normalise import normalise_default
from ukstt.score import align
from ukstt.stats import SpeakerCounts, bootstrap_ci, pooled_wer

UTTERANCE_COLUMNS = ("run_id", "clip_id", "set", "speaker_id", "region", "task", "status", "n_ref", "n_hyp",
                     "hits", "subs", "dels", "ins", "wer", "n_digit_tokens_hyp", "source")
SPEAKER_COLUMNS = ("region", "task", "speaker_id", "n_clips", "n_ref", "subs", "dels", "ins", "errors", "wer")
REGION_COLUMNS = ("task", "region", "n_speakers", "n_clips", "n_excluded", "n_ref", "subs", "dels", "ins",
                  "wer", "ci_lo", "ci_hi", "low_n")
PAIRWISE_COLUMNS = ("task", "region", "n_spk_region", "n_spk_base", "wer_region", "wer_base", "diff", "low_n")
ERROR_PAIR_COLUMNS = ("task", "region", "type", "ref_word", "hyp_word", "count")
PAIR_TYPES = {"S": "sub", "D": "del", "I": "ins"}


def n_digit_tokens_hyp(text: str) -> int:
    """Whitespace-separated tokens of the raw hypothesis that contain a digit."""
    return sum(any(ch.isdigit() for ch in token) for token in text.split())


def _failed_clips(run_dir: Path) -> set[str]:
    """Clips whose latest transcribe_log.csv row is `failed`."""
    log = run_dir / "transcribe_log.csv"
    latest = {row["clip_id"]: row["status"] for row in read_csv(log)} if log.exists() else {}
    return {clip_id for clip_id, status in latest.items() if status == "failed"}


def _region_order(region: str) -> tuple[int, str]:
    return (PILOT_REGIONS.index(region) if region in PILOT_REGIONS else len(PILOT_REGIONS), region)


def _hypothesis_text(raw_path: Path, clip_id: str) -> str:
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except ValueError as exc:  # corrupt JSON or bad UTF-8
        raise ValueError(f"{clip_id}: bad raw file {raw_path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
        raise ValueError(f"{clip_id}: bad raw file {raw_path}: expected a JSON object with a string 'text'")
    return raw["text"]


def _bool(value: bool) -> str:
    return "true" if value else "false"


def score_run(run_dir: Path, clips_csv: Path, out_dir: Path) -> None:
    """Write utterance_scores.csv, speaker_scores.csv and error_pairs.csv into out_dir."""
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    failed = _failed_clips(run_dir)
    utterances = []
    speakers = defaultdict(lambda: Counter())  # (region, task, speaker_id) -> counts
    pairs = defaultdict(Counter)  # (task, region) -> Counter of (type, ref_word, hyp_word)

    clips = read_csv(clips_csv)
    ids = [c["clip_id"] for c in clips]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate clip_id in {clips_csv}: {', '.join(duplicates)}")
    for clip in sorted(clips, key=lambda c: c["clip_id"]):
        clip_id, pilot = clip["clip_id"], clip["set"] == "pilot"
        row = dict.fromkeys(UTTERANCE_COLUMNS, "")
        row.update(run_id=run_dir.name, clip_id=clip_id, set=clip["set"], speaker_id=clip["speaker_id"],
                   region=clip["region"], task=clip["task"], source=clip["source"])

        ref = None
        if clip["reference_path"]:
            ref = normalise_default(Path(clip["reference_path"]).read_text(encoding="utf-8-sig", errors="replace"))
            if not ref:
                raise ValueError(f"{clip_id}: the reference has no words")
            row["n_ref"] = len(ref)

        raw_path = run_dir / "raw" / f"{clip_id}.json"
        if not raw_path.exists():
            row["status"] = "failed" if clip_id in failed else "missing"
        else:
            text = _hypothesis_text(raw_path, clip_id)
            hyp = normalise_default(text)
            row.update(n_hyp=len(hyp), n_digit_tokens_hyp=n_digit_tokens_hyp(text))
            if ref is None:
                row["status"] = "no_reference"
            else:
                a = align(ref, hyp)
                row.update(status="ok", hits=a.hits, subs=a.subs, dels=a.dels, ins=a.ins, wer=fmt_float(a.wer))
                if pilot:
                    total = speakers[(clip["region"], clip["task"], clip["speaker_id"])]
                    total.update(n_clips=1, n_ref=a.n_ref, subs=a.subs, dels=a.dels, ins=a.ins)
                    pairs[(clip["task"], clip["region"])].update(
                        (PAIR_TYPES[k], r or "", h or "") for k, r, h in a.ops if k != "H")
        utterances.append(row)

    speaker_rows = []
    for (region, task, speaker_id), t in sorted(speakers.items(), key=lambda kv: (kv[0][1], _region_order(kv[0][0]), kv[0][2])):
        errors = t["subs"] + t["dels"] + t["ins"]
        speaker_rows.append({"region": region, "task": task, "speaker_id": speaker_id, "n_clips": t["n_clips"],
                             "n_ref": t["n_ref"], "subs": t["subs"], "dels": t["dels"], "ins": t["ins"],
                             "errors": errors, "wer": fmt_float(errors / t["n_ref"])})
    pair_rows = []
    for (task, region), counter in sorted(pairs.items(), key=lambda kv: (kv[0][0], _region_order(kv[0][1]))):
        for (kind, r, h), count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0][1], kv[0][2], kv[0][0])):
            pair_rows.append({"task": task, "region": region, "type": kind, "ref_word": r, "hyp_word": h,
                              "count": count})

    write_csv(out_dir / "utterance_scores.csv", utterances, UTTERANCE_COLUMNS)
    write_csv(out_dir / "speaker_scores.csv", speaker_rows, SPEAKER_COLUMNS)
    write_csv(out_dir / "error_pairs.csv", pair_rows, ERROR_PAIR_COLUMNS)


def stats_run(out_dir: Path) -> None:
    """Read utterance_scores.csv and speaker_scores.csv; write region_summary.csv and pairwise_vs_baseline.csv."""
    out_dir = Path(out_dir)
    if not (out_dir / "utterance_scores.csv").exists():
        raise ValueError(f"run score first (no utterance_scores.csv in {out_dir})")
    pilot = [r for r in read_csv(out_dir / "utterance_scores.csv") if r["set"] == "pilot"]
    speakers = defaultdict(list)  # (task, region) -> [SpeakerCounts]
    totals = defaultdict(Counter)
    for r in read_csv(out_dir / "speaker_scores.csv"):
        key = (r["task"], r["region"])
        speakers[key].append(SpeakerCounts(r["speaker_id"], int(r["errors"]), int(r["n_ref"])))
        totals[key].update({k: int(r[k]) for k in ("n_ref", "subs", "dels", "ins")})

    summary, wer = [], {}
    for task, region in sorted({(r["task"], r["region"]) for r in pilot}, key=lambda k: (k[0], _region_order(k[1]))):
        clips = [r for r in pilot if (r["task"], r["region"]) == (task, region)]
        sp, t = speakers[(task, region)], totals[(task, region)]
        wer[(task, region)] = pooled_wer(sp) if sp else None
        ci = bootstrap_ci(sp, f"{task}|{region}")
        summary.append({"task": task, "region": region, "n_speakers": len(sp),
                        "n_clips": sum(r["status"] == "ok" for r in clips),
                        "n_excluded": sum(r["status"] != "ok" for r in clips),
                        "n_ref": t["n_ref"], "subs": t["subs"], "dels": t["dels"], "ins": t["ins"],
                        "wer": fmt_float(wer[(task, region)]),
                        "ci_lo": fmt_float(ci[0] if ci else None), "ci_hi": fmt_float(ci[1] if ci else None),
                        "low_n": _bool(len(sp) < MIN_SPEAKERS_CI)})

    pairwise = []
    for row in summary:
        task, region = row["task"], row["region"]
        if region == BASELINE:
            continue
        base = next((s for s in summary if (s["task"], s["region"]) == (task, BASELINE)), None)
        w, wb = wer[(task, region)], wer.get((task, BASELINE))
        pairwise.append({"task": task, "region": region, "n_spk_region": row["n_speakers"],
                         "n_spk_base": base["n_speakers"] if base else 0, "wer_region": row["wer"],
                         "wer_base": fmt_float(wb), "diff": fmt_float(w - wb if w is not None and wb is not None else None),
                         "low_n": _bool(row["low_n"] == "true" or base is None or base["low_n"] == "true")})

    write_csv(out_dir / "region_summary.csv", summary, REGION_COLUMNS)
    write_csv(out_dir / "pairwise_vs_baseline.csv", pairwise, PAIRWISE_COLUMNS)
