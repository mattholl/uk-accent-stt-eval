"""Deterministic synthetic clips and references for exercising the pipeline without real data."""

import hashlib
import math
import random
from pathlib import Path

from ukstt.audio import write_test_wav
from ukstt.constants import PILOT_REGIONS, SEED
from ukstt.csvio import write_csv
from ukstt.manifest import IN_COLUMNS

VOCAB = (
    "apple bridge candle dragon engine forest garden harbour island jacket kettle ladder meadow needle "
    "orchard pebble quarry river saddle tunnel umbrella valley window yellow zipper anchor basket cabin "
    "dolphin ember feather glacier hammer iron jungle kernel lantern magnet nectar oyster pillow quilt "
    "rocket sparrow timber velvet walnut yarn zephyr arrow button compass"
).split()
DEMO_CLIPS = 3
DEMO_SECONDS = 5.0


def make_dummy_data(out_dir: Path, clips_per_region: int = 4, speakers_per_region: int = 2,
                    seconds: float = 20, words: int = 50, seed: int = SEED) -> None:
    """Write out_dir/{manifests/clips_in.csv, recordings/*.wav, references/*.txt}."""
    if min(clips_per_region, speakers_per_region, words) < 1:
        raise ValueError("clips_per_region, speakers_per_region and words must be at least 1")
    if not (math.isfinite(seconds) and seconds > 0):
        raise ValueError("seconds must be a finite number above 0")
    out_dir = Path(out_dir)
    rows = []

    def add_clip(clip_id, set_name, speaker, region, task, secs, with_reference):
        audio = out_dir / "recordings" / f"{clip_id}.wav"
        write_test_wav(audio, secs, seed=int(hashlib.sha256(clip_id.encode()).hexdigest()[:8], 16))
        ref = ""
        if with_reference:
            path = out_dir / "references" / f"{clip_id}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            rng = random.Random(f"{seed}:{clip_id}")
            path.write_text(" ".join(rng.choices(VOCAB, k=words)) + "\n", encoding="utf-8", newline="\n")
            ref = path.as_posix()
        rows.append({"clip_id": clip_id, "set": set_name, "speaker_id": speaker, "region": region,
                     "task": task, "audio_path": audio.as_posix(), "reference_path": ref,
                     "source": "dummy", "notes": ""})

    for region in PILOT_REGIONS:
        taken = [0] * speakers_per_region
        for k in range(clips_per_region):
            s = k % speakers_per_region
            taken[s] += 1
            speaker = f"{region}_{s + 1:02d}"
            add_clip(f"{speaker}_{taken[s]:02d}", "pilot", speaker, region, "read", seconds, True)
    for n in range(1, DEMO_CLIPS + 1):
        clip_id = f"demo_{n:02d}"
        add_clip(clip_id, "demo", clip_id, "unknown", "unknown", DEMO_SECONDS, False)
    write_csv(out_dir / "manifests" / "clips_in.csv", rows, IN_COLUMNS)
