"""CSV helpers: UTF-8, LF line endings, atomic writes."""

import csv
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV with a header row; accepts LF and CRLF line endings and a UTF-8 BOM."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    """Write via a temporary file and os.replace, so a reader never sees a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def fmt_float(x: float | None) -> str:
    """Empty cell for None or NaN, else six decimals."""
    if x is None or math.isnan(x):
        return ""
    return f"{x:.6f}"
