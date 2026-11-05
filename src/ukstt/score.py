"""Word-level alignment and error counts (plan section 7)."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Alignment:
    n_ref: int
    n_hyp: int
    hits: int
    subs: int
    dels: int
    ins: int
    ops: tuple[tuple[str, str | None, str | None], ...]  # ('H'|'S'|'D'|'I', ref_word, hyp_word)

    @property
    def errors(self) -> int:
        return self.subs + self.dels + self.ins

    @property
    def wer(self) -> float | None:
        """(S+D+I)/N, never clipped. None iff n_ref == 0."""
        return self.errors / self.n_ref if self.n_ref else None


def align(ref: Sequence[str], hyp: Sequence[str]) -> Alignment:
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    d[0] = list(range(m + 1))
    for i in range(1, n + 1):
        d[i][0] = i
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)

    ops: list[tuple[str, str | None, str | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i == 0:
            ops.append(("I", None, hyp[j - 1]))
            j -= 1
        elif j == 0:
            ops.append(("D", ref[i - 1], None))
            i -= 1
        elif ref[i - 1] == hyp[j - 1] and d[i][j] == d[i - 1][j - 1]:
            ops.append(("H", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j - 1] + 1:
            ops.append(("S", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            ops.append(("D", ref[i - 1], None))
            i -= 1
        else:
            ops.append(("I", None, hyp[j - 1]))
            j -= 1
    ops.reverse()

    kinds = [op[0] for op in ops]
    return Alignment(n_ref=n, n_hyp=m, hits=kinds.count("H"), subs=kinds.count("S"),
                     dels=kinds.count("D"), ins=kinds.count("I"), ops=tuple(ops))
