"""Text normalisation, applied identically to reference and hypothesis (plan section 6)."""

import csv
import re
import types
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from ukstt.numwords import expand_numbers

_CHAR_MAP = {
    **dict.fromkeys(map(ord, "\u2019\u2018\u02bc\u2032`"), "'"),
    **dict.fromkeys(map(ord, "\u201c\u201d"), '"'),
    # en and em dash, NBSP, zero-width space/non-joiner/joiner, word joiner, BOM
    **dict.fromkeys(map(ord, "\u2013\u2014\u00a0\u200b\u200c\u200d\u2060\ufeff"), " "),
}
_BRACKETS = re.compile(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>")
_CAUSE = re.compile(r"(?<!\w)'cause\b")
_SEPARATORS = re.compile(r"[-_/]")
_PUNCTUATION = re.compile(r"[^\w\s']")
_EDGE_APOSTROPHE = re.compile(r"(?<![^\W\d_])'|'(?![^\W\d_])")  # not between two letters
_CLASSES = frozenset({"register", "orthography", "spelling", "filler"})


def _clean(token: str) -> bool:
    """True if normalise leaves the token alone, so it is already in normalised single-token form."""
    return normalise(token, {}, frozenset()) == [token]


def load_normalise_csv(path: Path = Path("config/normalise.csv")) -> tuple[dict[str, str], frozenset[str]]:
    """Return (token map, fillers) from a `from,to,class` file; every failure is a ValueError naming the file."""
    try:
        return _load_csv(path)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _load_csv(path: Path) -> tuple[dict[str, str], frozenset[str]]:
    mapping: dict[str, str] = {}
    fillers: set[str] = set()
    lines: dict[str, int] = {}  # line of each mapping row, for the chain check below
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        if next(reader, None) != ["from", "to", "class"]:
            raise ValueError(f"{path}: line 1: header must be exactly from,to,class")
        for row in reader:
            where = f"{path}: line {reader.line_num}"
            if not row:
                continue
            if len(row) != 3:
                raise ValueError(f"{where}: expected 3 columns, got {len(row)}")
            src, dst, cls = row
            if cls not in _CLASSES:
                raise ValueError(f"{where}: unknown class {cls!r} for {src!r}")
            if src in mapping or src in fillers:
                raise ValueError(f"{where}: duplicate entry {src!r}")
            if not _clean(src):
                raise ValueError(f"{where}: {src!r} is not in normalised single-token form")
            if cls == "filler":
                if dst:
                    raise ValueError(f"{where}: filler {src!r} must have an empty 'to'")
                fillers.add(src)
                continue
            if not dst:
                raise ValueError(f"{where}: {src!r} needs a 'to'")
            words = dst.split(" ")
            for word in words:
                if not word:
                    raise ValueError(f"{where}: 'to' for {src!r} has an empty word (extra space?)")
                if not _clean(word):
                    raise ValueError(f"{where}: 'to' word {word!r} is not clean normalised text")
            mapping[src] = dst
            lines[src] = reader.line_num
    if not mapping and not fillers:
        raise ValueError(f"{path}: no data rows")
    for src, dst in mapping.items():  # outputs are never inputs: no chains or loops, and no fillers
        for word in dst.split(" "):
            if word in mapping or word in fillers:
                raise ValueError(f"{path}: line {lines[src]}: 'to' word {word!r} is a filler or another 'from' (chain or loop)")
    return mapping, frozenset(fillers)


def normalise(text: str, mapping: Mapping[str, str], fillers: frozenset[str]) -> list[str]:
    s = unicodedata.normalize("NFKC", text).translate(_CHAR_MAP).lower()  # rules 1, 2
    s = unicodedata.normalize("NFKC", s)  # lower() can leave non-NFKC text ("İ")
    s = _BRACKETS.sub(" ", s)  # 3
    s = _CAUSE.sub(" because ", s)  # 4
    s = expand_numbers(s)  # 5
    s = _SEPARATORS.sub(" ", s)  # 6
    s = _PUNCTUATION.sub(" ", s)  # 7
    s = _EDGE_APOSTROPHE.sub(" ", s)
    tokens = [w for t in s.split() for w in mapping.get(t, t).split()]  # 8, 9
    return [t for t in tokens if t not in fillers]  # 10, 11


@lru_cache(maxsize=1)
def _default_tables() -> tuple[Mapping[str, str], frozenset[str]]:
    mapping, fillers = load_normalise_csv()
    return types.MappingProxyType(mapping), fillers


def normalise_default(text: str) -> list[str]:
    mapping, fillers = _default_tables()
    return normalise(text, mapping, fillers)
