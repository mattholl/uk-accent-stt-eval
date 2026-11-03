#!/usr/bin/env python3
"""Fetch a few samples per dialect from ylacombe/english_dialects (a Hugging Face copy of OpenSLR SLR83).

Uses the public datasets-server rows API (no 9 GB download, no API key). Writes:
  data/audio/<clip_id>.wav            local audio (gitignored)
  references/<clip_id>.txt            the dataset's transcript
  manifests/clips_in.csv              the file `ukstt build-manifest` will read
Run from the repo root:  python3 scripts/fetch_english_dialects_samples.py [--speakers 2] [--clips 3]
Male configs only, so gender is held constant (irish exists only as male in this dataset).
"""
import argparse, csv, json, time, urllib.error, urllib.parse, urllib.request, wave
from pathlib import Path

DATASET = "ylacombe/english_dialects"
LABELS = ["irish", "midlands", "northern", "scottish", "southern", "welsh"]
API = "https://datasets-server.huggingface.co/rows"


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speakers", type=int, default=2)
    ap.add_argument("--clips", type=int, default=3)
    ap.add_argument("--max-seconds", type=float, default=12.0)
    a = ap.parse_args()
    root = Path(".")
    (root / "data/audio").mkdir(parents=True, exist_ok=True)
    (root / "references").mkdir(exist_ok=True)
    (root / "manifests").mkdir(exist_ok=True)
    out = []
    for label in LABELS:
        cfg = f"{label}_male"
        first = rows(cfg, 0, 1)
        total = first["num_rows_total"]
        # scan about 8 evenly spaced windows to find distinct speakers
        step = max(1, total // 8)
        found: dict[int, list[dict]] = {}
        for off in range(0, total, step):
            d = rows(cfg, off, min(30, total - off))
            for r in d["rows"]:
                found.setdefault(r["row"]["speaker_id"], []).append(r["row"])
        ranked = sorted(found, key=lambda s: -len(found[s]))[: a.speakers]
        print(f"{cfg}: {total} rows, {len(found)} speakers seen, using {ranked}")
        for spk in ranked:
            taken = 0
            for row in found[spk]:
                if taken >= a.clips:
                    break
                text = row["text"].strip()
                clip_id = f"{label}_{spk}_{row['line_id'].lower()}"
                wav = root / "data/audio" / f"{clip_id}.wav"
                if not wav.exists():
                    wav.write_bytes(get(row["audio"][0]["src"], binary=True))
                with wave.open(str(wav)) as w:
                    dur, sr, ch, sw = w.getnframes() / w.getframerate(), w.getframerate(), w.getnchannels(), w.getsampwidth()
                if dur > a.max_seconds:
                    wav.unlink()
                    continue
                (root / "references" / f"{clip_id}.txt").write_text(text + "\n", encoding="utf-8")
                out.append(dict(clip_id=clip_id, set="pilot", speaker_id=f"{label}_{spk}", region=label, task="read",
                                audio_path=f"data/audio/{clip_id}.wav", reference_path=f"references/{clip_id}.txt",
                                source=f"{DATASET}:{cfg}", notes=f"line_id={row['line_id']} sr={sr} ch={ch} bits={sw*8} dur={dur:.2f}"))
                taken += 1
    path = root / "manifests/clips_in.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0]))
        wr.writeheader()
        wr.writerows(out)
    print(f"wrote {len(out)} clips -> {path}")


if __name__ == "__main__":
    main()
