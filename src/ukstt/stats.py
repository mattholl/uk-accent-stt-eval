"""Speaker-level statistics (plan section 8). Stdlib only."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from ukstt.constants import ALPHA, B, MIN_SPEAKERS_CI, SEED


@dataclass(frozen=True)
class SpeakerCounts:
    speaker_id: str
    errors: int
    n_ref: int


def pooled_wer(sp: Sequence[SpeakerCounts]) -> float:
    """Micro average over speakers: sum of errors / sum of reference words."""
    n_ref = sum(s.n_ref for s in sp)
    if n_ref == 0:
        raise ValueError("no reference words")
    return sum(s.errors for s in sp) / n_ref


def percentile_interval(sorted_reps: Sequence[float], alpha: float = ALPHA) -> tuple[float, float]:
    """(reps[int(B*a/2)], reps[int(B*(1-a/2))-1]) for B = len(sorted_reps); the input must be sorted."""
    n = len(sorted_reps)
    if n == 0:
        raise ValueError("no bootstrap replicates")
    return sorted_reps[int(n * alpha / 2)], sorted_reps[int(n * (1 - alpha / 2)) - 1]


def bootstrap_ci(sp: Sequence[SpeakerCounts], key: str, B: int = B,
                 seed: int = SEED) -> tuple[float, float] | None:
    """95% percentile bootstrap over speakers; None below MIN_SPEAKERS_CI speakers
    with reference words (zero-word speakers are dropped).

    `key` names the stratum (e.g. "read|welsh"): the same key always gives the same interval.
    """
    if any(s.n_ref < 0 or s.errors < 0 for s in sp):
        raise ValueError("negative error or reference-word count")
    sp = sorted((s for s in sp if s.n_ref > 0), key=lambda s: s.speaker_id)  # input order must not matter
    if len(sp) < MIN_SPEAKERS_CI:
        return None
    rng = random.Random(f"{seed}:{key}")
    reps = sorted(pooled_wer(rng.choices(sp, k=len(sp))) for _ in range(B))
    return percentile_interval(reps)
