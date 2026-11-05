"""WAV probing and test-audio generation, stdlib only."""

import hashlib
import os
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WavInfo:
    sample_rate_hz: int
    channels: int
    sampwidth_bytes: int
    n_frames: int
    duration_s: float


def probe_wav(path: Path) -> WavInfo:
    """Header facts of a PCM WAV file. Anything the wave module cannot read is a ValueError."""
    try:
        with wave.open(str(path), "rb") as wf:
            rate, n_frames = wf.getframerate(), wf.getnframes()
            info = WavInfo(rate, wf.getnchannels(), wf.getsampwidth(), n_frames,
                           n_frames / rate if rate else 0.0)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"{path}: not a readable PCM WAV file ({exc})") from exc
    if os.path.getsize(path) < n_frames * info.sampwidth_bytes * info.channels:
        raise ValueError(f"{path}: truncated WAV file (the header promises more audio than the file holds)")
    return info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_test_wav(path: Path, seconds: float, sample_rate_hz: int = 16000, seed: int = 0) -> None:
    """Mono PCM16 WAV of low-amplitude seeded noise."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    n = round(seconds * sample_rate_hz)
    samples = rng.choices(range(-500, 501), k=n)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate_hz)
        wf.writeframes(struct.pack(f"<{n}h", *samples))
