"""Digits to British English words, for the normaliser (plan section 6, rule 5)."""

import re

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_MAX = 999_999_999

# Ordinals 1st..31st (the only ones expanded).
_ORDINALS = dict(enumerate(
    ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
     "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth").split(), 1))
for _n in range(21, 30):
    _ORDINALS[_n] = "twenty " + _ORDINALS[_n - 20]
_ORDINALS[30] = "thirtieth"
_ORDINALS[31] = "thirty first"

_POUNDS = re.compile(r"£([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)(?!\w)")
_PERCENT = re.compile(r"(?<![0-9,.])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)%(?!\w)")
_THOUSANDS = re.compile(r"(?<=[0-9]),(?=[0-9]{3}(?![0-9]))")
# integer, optional decimals, optional ordinal suffix; not touching a letter, digit, or "_" on either side
_NUMBER = re.compile(r"(?<![^\W_])([0-9]+)(?:\.([0-9]+))?(st|nd|rd|th)?(?![^\W_])", re.IGNORECASE)
_MAX_DIGITS = 9


def _below_1000(n: int) -> str:
    """1..999, with the British "and" after the hundreds."""
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        if hundreds:
            parts.append("and")
        if rest < 20:
            parts.append(_ONES[rest])
        else:
            tens, units = divmod(rest, 10)
            parts.append(_TENS[tens])
            if units:
                parts.append(_ONES[units])
    return " ".join(parts)


def int_to_words(n: int) -> str:
    """0..999,999,999 as British cardinal words: 21 -> "twenty one", 105 -> "one hundred and five"."""
    if not 0 <= n <= _MAX:
        raise ValueError(f"int_to_words supports 0..{_MAX}, got {n}")
    if n == 0:
        return "zero"
    parts: list[str] = []
    for group, name in ((n // 1_000_000, "million"), (n // 1000 % 1000, "thousand"), (n % 1000, "")):
        if not group:
            continue
        words = _below_1000(group)
        if name:
            words += " " + name
        elif parts and group < 100:
            words = "and " + words  # one thousand and one
        parts.append(words)
    return " ".join(parts)


def _expand_match(m: re.Match) -> str:
    whole, frac, suffix = m.groups()
    if len(whole) > _MAX_DIGITS:
        return m.group(0)  # huge numbers are left untouched
    if len(whole) > 1 and whole[0] == "0":  # leading zero ("007"): left as written; only decimals are spoken, for idempotence
        if frac is None:
            return m.group(0)
        return f"{whole} point " + " ".join(_ONES[int(c)] for c in frac)
    n = int(whole)
    if suffix:
        return _ORDINALS[n] if frac is None and n in _ORDINALS else m.group(0)
    words = int_to_words(n)
    if frac is not None:
        words += " point " + " ".join(_ONES[int(c)] for c in frac)
    return words


def expand_numbers(text: str) -> str:
    """Pounds, per cent, thousands commas, decimals, ordinals 1st..31st, then integers."""
    text = _POUNDS.sub(r"\1 pounds", text)
    text = _PERCENT.sub(r"\1 per cent", text)
    text = _THOUSANDS.sub("", text)
    return _NUMBER.sub(_expand_match, text)
