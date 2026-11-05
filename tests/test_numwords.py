import pytest

from ukstt.numwords import expand_numbers, int_to_words


@pytest.mark.parametrize("n, words", [
    (0, "zero"),
    (13, "thirteen"),
    (20, "twenty"),
    (21, "twenty one"),
    (100, "one hundred"),
    (105, "one hundred and five"),
    (110, "one hundred and ten"),
    (1000, "one thousand"),
    (1001, "one thousand and one"),
    (1100, "one thousand one hundred"),
    (1984, "one thousand nine hundred and eighty four"),
    (100_000, "one hundred thousand"),
    (999_999, "nine hundred and ninety nine thousand nine hundred and ninety nine"),
    (1_000_000, "one million"),
    (1_000_001, "one million and one"),
    (1_000_100, "one million one hundred"),
    (999_999_999, "nine hundred and ninety nine million nine hundred and ninety nine thousand "
                  "nine hundred and ninety nine"),
])
def test_int_to_words(n, words):
    assert int_to_words(n) == words


def test_int_to_words_never_hyphenates_or_double_spaces():
    for n in range(2001):
        words = int_to_words(n)
        assert "-" not in words
        assert words == " ".join(words.split())


@pytest.mark.parametrize("n", [-1, 1_000_000_000])
def test_int_to_words_out_of_range(n):
    with pytest.raises(ValueError):
        int_to_words(n)


@pytest.mark.parametrize("text, expected", [
    ("I have 5 cats.", "I have five cats."),
    ("£5", "five pounds"),
    ("£5.50", "five point five zero pounds"),
    ("£1,000", "one thousand pounds"),
    ("3.5%", "three point five per cent"),
    ("50%", "fifty per cent"),
    ("1,000,000", "one million"),
    ("0.5", "zero point five"),
    ("7:30", "seven:thirty"),
    ("10-20", "ten-twenty"),
    ("1st 2nd 3rd 4th 21st 31st", "first second third fourth twenty first thirty first"),
    ("It's £5, 1,000 and 3.5%", "It's five pounds, one thousand and three point five per cent"),
])
def test_expand_numbers(text, expected):
    assert expand_numbers(text) == expected


@pytest.mark.parametrize("text", ["007", "01st", "007th", "5pm", "1990s", "c2c", "32nd", "3.5th", "1234567890", "£5m"])
def test_expand_numbers_leaves_these_untouched(text):
    assert expand_numbers(text) == text


@pytest.mark.parametrize("text, expected", [
    (".5", ".five"),
    ("x.5", "x.five"),
    ("0_1", "zero_one"),
    ("1_000", "one_000"),
    ("a_5_b", "a_five_b"),
    ("3.5.2", "three point five.two"),
])
def test_expand_numbers_separators(text, expected):
    assert expand_numbers(text) == expected


def test_expand_numbers_ignores_ten_digit_runs_without_converting_them():
    assert expand_numbers("1" * 4301) == "1" * 4301
    assert expand_numbers("1" * 4301 + "%") == "1" * 4301 + " per cent"
    assert expand_numbers("1234567890.5") == "1234567890.5"
