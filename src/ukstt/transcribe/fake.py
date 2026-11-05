"""Offline backend: the reference text with seeded, region-dependent word errors."""

import random
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

from ukstt.constants import SEED
from ukstt.csvio import read_csv
from ukstt.transcribe.base import ConnectError, HttpError, ReadTimeout

NONSENSE = (
    "blorp frindle zanth quibbet morvane tessik plunder jorvik wibble snarf glimmet "
    "dravok ploom trundle yarbles cwenth fobble krindle vesper lorquat nimbus sprockle "
    "hobnail quarrel zindle mubble tarvish elphin brackle ondrey pimsy ruddock jessamy"
).split()
NO_REFERENCE_TEXT = "This is a fake transcript."


class FakeTranscriber:
    """Looks everything up by the audio file stem, which is the clip_id."""

    name = "fake"

    def __init__(self, references: Mapping[str, str], region_of: Mapping[str, str],
                 error_rates: Mapping[str, float],
                 failures: Mapping[str, Sequence[str]] | None = None, seed: int = SEED) -> None:
        self.references = dict(references)
        self.region_of = dict(region_of)
        self.error_rates = dict(error_rates)
        self.failures = {k: list(v) for k, v in (failures or {}).items()}  # one entry consumed per attempt
        self.seed = seed

    def transcribe(self, audio_path: Path, params: Mapping[str, object]) -> dict:
        clip_id = Path(audio_path).stem
        queue = self.failures.get(clip_id)
        if queue:
            token = queue.pop(0)
            if token in ("429", "500", "503"):
                raise HttpError(int(token), "fake failure", retry_after=1.0 if token == "429" else None)
            if token == "connect":
                raise ConnectError("fake connect error")
            if token == "timeout":
                raise ReadTimeout("fake read timeout")
            if token == "empty":
                return _response([])
            if token == "malformed":
                return {"oops": 1}
            raise ValueError(f"unknown failure token {token!r}")
        if clip_id not in self.references:
            return _response(NO_REFERENCE_TEXT.rstrip(".").split(), NO_REFERENCE_TEXT)
        rate = self.error_rates[self.region_of.get(clip_id, "unknown")]
        rng = random.Random(f"{self.seed}:{clip_id}")
        out: list[str] = []
        for word in self.references[clip_id].split():
            if rng.random() >= rate:
                out.append(word)
                continue
            kind = rng.randrange(3)  # substitute, delete or insert
            if kind == 0:
                out.append(_other(rng, word))
            elif kind == 2:
                out += [word, _other(rng, word)]
        text = " ".join(out)
        text = text[:1].upper() + text[1:] + "." if text else ""
        return _response(out, text)

    @classmethod
    def from_clips(cls, clips_csv: Path, fake_toml: Path, repo_root: Path = Path(".")) -> "FakeTranscriber":
        with open(fake_toml, "rb") as fh:
            try:
                data = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                raise ValueError(f"{fake_toml}: {exc}") from exc
        rates = data.get("error_rates")
        if not isinstance(rates, dict) or not rates:
            raise ValueError(f"{fake_toml}: missing [error_rates] table")
        references, region_of = {}, {}
        for row in read_csv(clips_csv):
            region_of[row["clip_id"]] = row["region"]
            if row.get("reference_path"):
                references[row["clip_id"]] = (Path(repo_root) / row["reference_path"]).read_text(
                    encoding="utf-8", errors="replace")
        for region in sorted(set(region_of.values())):
            if region not in rates:
                raise ValueError(f"{fake_toml}: no error rate for region {region!r}")
        return cls(references, region_of, rates)


def _other(rng: random.Random, word: str) -> str:
    """A nonsense word that differs from `word`."""
    choice = rng.choice(NONSENSE)
    while choice == word.lower():
        choice = rng.choice(NONSENSE)
    return choice


def _response(words: list[str], text: str | None = None) -> dict:
    items = [{"text": w, "start": round(i * 0.4, 2), "end": round(i * 0.4 + 0.35, 2), "type": "word"}
             for i, w in enumerate(words)]
    return {"language_code": "eng", "language_probability": 1.0,
            "text": " ".join(words) if text is None else text, "words": items}
