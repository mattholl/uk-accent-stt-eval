#!/usr/bin/env python3
"""Fetch samples per dialect from ylacombe/english_dialects (a Hugging Face copy of OpenSLR SLR83).

Uses the public datasets-server rows API (no 9 GB download, no API key). Writes:
  data/audio/<clip_id>.wav     local audio (gitignored; an existing file is not downloaded again)
  references/<clip_id>.txt     the dataset's transcript
  <--out>                      the file `ukstt build-manifest` reads (default manifests/clips_in.csv)
  data/hf_speakers.json        cache of the speaker scan (delete it to rescan)

Run from the repo root:
  python3 scripts/fetch_english_dialects_samples.py --list [--genders both]
  python3 scripts/fetch_english_dialects_samples.py [--speakers 2] [--clips 3]              # clips per speaker
  python3 scripts/fetch_english_dialects_samples.py --speakers 3 --clips-per-label 60 --out manifests/clips_in_large.csv \\
      --exclude-from manifests/clips_in.csv

Every config (<label>_male, <label>_female) is treated as one label. Per label, the chosen speakers are the ones
with the most rows (ties: lowest speaker id); a label with fewer speakers than --speakers uses what exists.
--clips-per-label N spreads N clips round-robin over them; if the label cannot reach N the script warns on
stderr and takes what exists. --exclude-from skips clip_ids already listed in that CSV (repeatable), so the
new clips are all different. Clips come in dataset order within a speaker; a clip longer than --max-seconds
is skipped and the next one is used.

Ids: clip_id = <label>_<key>_<line_id lowercase>, speaker_id = <label>_<key>. The key is the dataset speaker
number for male configs (so existing ids do not change) and "f" + the number for female configs, because the
same number can occur in a male and a female subset. Irish has no female subset.
"""
import argparse, csv, json, sys, time, urllib.error, urllib.parse, urllib.request, wave
from pathlib import Path

DATASET = "ylacombe/english_dialects"
LABELS = ["irish", "midlands", "northern", "scottish", "southern", "welsh"]
API = "https://datasets-server.huggingface.co/rows"
CACHE = Path("data/hf_speakers.json")


def get(url: str, binary: bool = False):
    for k in range(8):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            return data if binary else json.loads(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or k == 7:
                raise
            time.sleep(5 * (k + 1))
    raise RuntimeError("unreachable")


def rows(config: str, offset: int, length: int) -> dict:
    q = urllib.parse.urlencode(dict(dataset=DATASET, config=config, split="train", offset=offset, length=length))
    time.sleep(1.5)
    return get(f"{API}?{q}")


def configs(genders: str) -> list[tuple[str, str, str]]:
    """(label, gender, config name); irish has no female subset."""
    wanted = ["male", "female"] if genders == "both" else [genders]
    return [(lab, g, f"{lab}_{g}") for lab in LABELS for g in wanted if (lab, g) != ("irish", "female")]


def key(gender: str, speaker) -> str:
    return str(speaker) if gender == "male" else f"f{speaker}"


def scan(cfg: str) -> dict:
    """The whole subset in pages of 100: {"rows": N, "speakers": {speaker_id: [[offset, line_id], ...]}}."""
    page, off, speakers = rows(cfg, 0, 100), 0, {}
    total = page["num_rows_total"]
    while page["rows"]:
        for i, r in enumerate(page["rows"]):
            speakers.setdefault(str(r["row"]["speaker_id"]), []).append([off + i, r["row"]["line_id"]])
        off += len(page["rows"])
        if off >= total:
            break
        page = rows(cfg, off, 100)
    if off != total:
        print(f"warning: {cfg}: scanned {off} of {total} rows", file=sys.stderr)
    return {"rows": total, "speakers": speakers}


def load_index(names: list[str], cache: Path = CACHE) -> dict:
    index = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for cfg in names:
        if cfg not in index:
            index[cfg] = scan(cfg)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(index), encoding="utf-8")  # kept after every subset: a crash loses little
    return index


def ranked(speakers: dict) -> list[str]:
    """Speaker ids, most rows first, ties by id."""
    return sorted(speakers, key=lambda s: (-len(speakers[s]), int(s)))


def allocate(available: list[int], total: int | None, per_speaker: int | None) -> list[int]:
    """Clips per speaker: per_speaker each, or `total` dealt round-robin; never more than a speaker has."""
    if per_speaker is not None:
        return [min(per_speaker, a) for a in available]
    quota, left = [0] * len(available), total
    while left and any(q < a for q, a in zip(quota, available)):
        for i, a in enumerate(available):
            if left and quota[i] < a:
                quota[i] += 1
                left -= 1
    return quota


def fetch_clip(cfg: str, offset: int, clip_id: str, root: Path) -> tuple[str, dict]:
    """Make sure the wav and the reference exist and the wav is sane; returns (text, info)."""
    wav, ref = root / "data/audio" / f"{clip_id}.wav", root / "references" / f"{clip_id}.txt"
    if wav.exists() and ref.exists():
        text = ref.read_text(encoding="utf-8").strip()
    else:
        row = rows(cfg, offset, 1)["rows"][0]["row"]
        text = row["text"].strip()
        if not wav.exists():
            tmp = wav.with_name(wav.name + ".part")
            tmp.write_bytes(get(row["audio"][0]["src"], binary=True))
            tmp.replace(wav)
        ref.write_text(text + "\n", encoding="utf-8")
    try:
        with wave.open(str(wav)) as w:
            info = dict(dur=w.getnframes() / w.getframerate(), sr=w.getframerate(), ch=w.getnchannels(), bits=w.getsampwidth() * 8)
    except (wave.Error, EOFError, ZeroDivisionError) as e:
        wav.unlink()
        raise SystemExit(f"error: {wav} is not a readable WAV ({e}); deleted, run again")
    if (info["ch"], info["bits"]) != (1, 16) or info["sr"] < 16000 or info["dur"] <= 0:
        wav.unlink()
        raise SystemExit(f"error: {wav} is not PCM16 mono >=16 kHz ({info}); deleted")
    return text, info


def excluded_ids(paths: list[Path]) -> set[str]:
    ids = set()
    for p in paths:
        with p.open(newline="", encoding="utf-8-sig") as f:
            ids.update(r["clip_id"] for r in csv.DictReader(f))
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch dialect samples (see the module docstring).")
    ap.add_argument("--list", action="store_true", help="print rows, speakers and rows per speaker per config; no audio")
    ap.add_argument("--speakers", type=int, default=2, help="at most this many speakers per label (default 2)")
    n = ap.add_mutually_exclusive_group()
    n.add_argument("--clips", type=int, help="clips per speaker (default 3)")
    n.add_argument("--clips-per-label", type=int, help="total clips per label, spread round-robin over the speakers")
    ap.add_argument("--max-seconds", type=float, default=12.0)
    ap.add_argument("--genders", choices=("male", "female", "both"), default="male")
    ap.add_argument("--out", type=Path, default=Path("manifests/clips_in.csv"))
    ap.add_argument("--exclude-from", type=Path, action="append", default=[], metavar="CSV",
                    help="skip clip_ids listed in this CSV (repeatable)")
    a = ap.parse_args(argv)
    if a.speakers < 1 or (a.clips or 1) < 1 or (a.clips_per_label or 1) < 1:
        ap.error("--speakers, --clips and --clips-per-label must be at least 1")
    root = Path(".")
    cfgs = configs(a.genders)
    index = load_index([c for _, _, c in cfgs], root / CACHE)

    if a.list:
        for _, g, cfg in cfgs:
            sp = index[cfg]["speakers"]
            print(f"{cfg}: {index[cfg]['rows']} rows, {len(sp)} speakers: "
                  + ", ".join(f"{key(g, s)} x{len(sp[s])}" for s in ranked(sp)))
        return 0

    exclude = excluded_ids(a.exclude_from)
    per_speaker = None if a.clips_per_label is not None else (a.clips or 3)
    (root / "data/audio").mkdir(parents=True, exist_ok=True)
    (root / "references").mkdir(exist_ok=True)
    out = []
    for label, g, cfg in cfgs:
        sp = index[cfg]["speakers"]
        chosen = ranked(sp)[: a.speakers]
        cands = {s: [(off, ln) for off, ln in sp[s] if f"{label}_{key(g, s)}_{ln.lower()}" not in exclude] for s in chosen}
        quota = allocate([len(cands[s]) for s in chosen], a.clips_per_label, per_speaker)
        wanted = a.clips_per_label if a.clips_per_label is not None else per_speaker * len(chosen)
        got = 0
        for s, q in zip(chosen, quota):
            taken = 0
            for off, line_id in cands[s]:
                if taken >= q:
                    break
                clip_id = f"{label}_{key(g, s)}_{line_id.lower()}"
                text, info = fetch_clip(cfg, off, clip_id, root)
                if info["dur"] > a.max_seconds:
                    (root / "data/audio" / f"{clip_id}.wav").unlink()
                    (root / "references" / f"{clip_id}.txt").unlink(missing_ok=True)
                    continue
                out.append(dict(clip_id=clip_id, set="pilot", speaker_id=f"{label}_{key(g, s)}", region=label, task="read",
                                audio_path=f"data/audio/{clip_id}.wav", reference_path=f"references/{clip_id}.txt",
                                source=f"{DATASET}:{cfg}",
                                notes=f"line_id={line_id} sr={info['sr']} ch={info['ch']} bits={info['bits']} dur={info['dur']:.2f}"))
                taken += 1
            got += taken
        print(f"{cfg}: {len(sp)} speakers, using {[key(g, s) for s in chosen]}, {got} clips")
        if got < wanted:
            print(f"warning: {cfg}: only {got} of {wanted} clips could be taken", file=sys.stderr)
    if not out:
        print("error: no clips selected; nothing written", file=sys.stderr)
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    print(f"wrote {len(out)} clips -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
