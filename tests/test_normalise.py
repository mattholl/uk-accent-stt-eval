from pathlib import Path

import random

import pytest

from ukstt.normalise import load_normalise_csv, normalise, normalise_default

ROOT = Path(__file__).resolve().parent.parent
MAPPING, FILLERS = load_normalise_csv(ROOT / "config" / "normalise.csv")


def norm(text):
    return normalise(text, MAPPING, FILLERS)


def test_normalise_default_matches_explicit_tables(monkeypatch):
    monkeypatch.chdir(ROOT)  # normalise_default reads config/normalise.csv relative to the cwd
    assert normalise_default("Um, gonna go") == norm("Um, gonna go") == ["going", "to", "go"]


@pytest.mark.parametrize("text, expected", [
    # rule 1: NFKC, quotes, dashes, NBSP, zero-width
    ("Don’t—stop!", ["don't", "stop"]),
    ("‘it’s’ ʼtis ′x′ `y`", ["it's", "tis", "x", "y"]),
    ("“Hi” there", ["hi", "there"]),
    ("a\u00a0b\u200bc–d", ["a", "b", "c", "d"]),
    ("ＡＢＣ １２", ["abc", "twelve"]),  # NFKC folds full-width forms
    # rule 2: lowercase
    ("HELLO World", ["hello", "world"]),
    # rule 3: bracketed spans
    ("a (b) [c] <d> e", ["a", "e"]),
    # rule 4: 'cause
    ("'cause", ["because"]),
    ("I did it ’cause I could", ["i", "did", "it", "because", "i", "could"]),
    ("cause and effect", ["cause", "and", "effect"]),
    # rule 5: numbers
    ("It's £5, 1,000 and 3.5%", ["it's", "five", "pounds", "one", "thousand", "and",
                                 "three", "point", "five", "per", "cent"]),
    ("7:30", ["seven", "thirty"]),
    ("1984", ["one", "thousand", "nine", "hundred", "and", "eighty", "four"]),
    ("the 5th of May", ["the", "fifth", "of", "may"]),
    ("007", ["007"]),
    ("5pm", ["5pm"]),
    ("C2c trains", ["c2c", "trains"]),
    # rule 6: separators
    ("well-known a_b a/b", ["well", "known", "a", "b", "a", "b"]),
    # rule 7: punctuation and apostrophes
    ("yes,no", ["yes", "no"]),
    ("u.s.", ["u", "s"]),
    ("dogs' 'quoted' rock'n'roll", ["dogs", "quoted", "rock'n'roll"]),
    ("what?! (really)...", ["what"]),
    # rule 9: mapping
    ("gonna", ["going", "to"]),
    ("I wanna go", ["i", "want", "to", "go"]),
    ("OK, alright, 10 percent", ["okay", "all", "right", "ten", "per", "cent"]),
    ("favorite color", ["favourite", "colour"]),
    ("recognize", ["recognise"]),
    # rule 10: fillers
    ("uh-huh", []),
    ("Um, the colour (laughs) [unclear] well-known", ["the", "colour", "well", "known"]),
    ("er erm hmm mhm", []),
    # dialect words and non-fillers are never touched
    ("nowt wee aye ah eh like yeah ye cannae", ["nowt", "wee", "aye", "ah", "eh", "like", "yeah", "ye", "cannae"]),
    # empty input
    ("", []),
    ("   ", []),
    ("(laughs)", []),
])
def test_normalise(text, expected):
    assert norm(text) == expected


def test_real_reference_with_digits():
    text = "One way flights from Lyon to Guangzhou leaving on the 5th of May start at 950 pounds"
    assert norm(text) == ("one way flights from lyon to guangzhou leaving on the fifth of may "
                          "start at nine hundred and fifty pounds").split()


@pytest.mark.parametrize("text", [
    "Don’t—stop!",
    "It's £5, 1,000 and 3.5%",
    "Um, the colour (laughs) [unclear] well-known",
    "'cause", "yes,no", "7:30", "uh-huh", "gonna", "1984", "007", "5pm", "C2c trains",
    "OK, alright, 10 percent", "dogs' 'quoted' rock'n'roll", "u.s. 1st 31st £5.50",
    ".5", "0_1", "1_000", "x.5", "1" * 4301, "İstanbul",
])
def test_idempotent(text):
    once = norm(text)
    assert norm(" ".join(once)) == once


def test_custom_tables():
    assert normalise("Foo bar baz", {"foo": "x y"}, frozenset({"bar"})) == ["x", "y", "baz"]


def test_normalise_csv_contents():
    assert MAPPING["gonna"] == "going to"
    assert MAPPING["cos"] == "because"
    assert {"um", "uh", "huh", "mhm"} <= FILLERS
    assert not FILLERS & set(MAPPING)
    assert not FILLERS & {"ah", "eh", "aye", "like", "yeah"}
    assert not set(MAPPING) & {"wee", "nowt", "aye", "ye", "youse", "cannae", "dinnae"}
    # outputs are never inputs, so one pass is enough and normalise stays idempotent
    assert all(word not in MAPPING and word not in FILLERS for to in MAPPING.values() for word in to.split())


def test_idempotence_fuzz():
    rng = random.Random(20261102)
    for _ in range(3000):
        text = "".join(rng.choice("0123456789._ abxst") for _ in range(rng.randint(1, 14)))
        once = norm(text)
        assert norm(" ".join(once)) == once, repr(text)


def load_text(tmp_path, body, header="from,to,class\n"):
    path = tmp_path / "n.csv"
    path.write_text(header + body, encoding="utf-8")
    return load_normalise_csv(path)


def test_load_normalise_csv_reads_valid_files(tmp_path):
    assert load_text(tmp_path, "a,b c,register\num,,filler\n") == ({"a": "b c"}, frozenset({"um"}))
    assert load_text(tmp_path, "a,b,register\n", header="\ufefffrom,to,class\n") == ({"a": "b"}, frozenset())  # BOM


@pytest.mark.parametrize("header, body, fragment", [
    ("from,to\n", "a,b\n", "header"),
    ("to,from,class\n", "a,b,register\n", "header"),
    ("from,to,class\n", "", "no data rows"),
    ("from,to,class\n", "a,b\n", "line 2"),
    ("from,to,class\n", "a,b,register,x\n", "line 2"),
    ("from,to,class\n", "a,b,nonsense\n", "unknown class"),
    ("from,to,class\n", "a,,register\n", "needs a 'to'"),
    ("from,to,class\n", "um,x,filler\n", "empty 'to'"),
    ("from,to,class\n", "A,b,register\n", "single-token"),
    ("from,to,class\n", "a b,c,register\n", "single-token"),
    ("from,to,class\n", "5,b,register\n", "single-token"),
    ("from,to,class\n", "a-b,c,register\n", "single-token"),
    ("from,to,class\n", "a,b,register\nc,d,register\na,e,spelling\n", "line 4"),
    ("from,to,class\n", "um,,filler\num,x,register\n", "line 3"),
    ("from,to,class\n", "a,B,register\n", "clean"),
    ("from,to,class\n", "a,b-c,register\n", "clean"),
    ("from,to,class\n", "a,5,register\n", "clean"),
    ("from,to,class\n", "a,um,register\num,,filler\n", "line 2"),
    ("from,to,class\n", "a,b  c,register\n", "empty word"),
    ("from,to,class\n", "a,b,register\nb,c,register\n", "line 2"),
    ("from,to,class\n", "a,a,register\n", "line 2"),
])
def test_load_normalise_csv_rejects(tmp_path, header, body, fragment):
    with pytest.raises(ValueError, match=fragment) as exc:
        load_text(tmp_path, body, header)
    assert "n.csv" in str(exc.value)


def test_load_normalise_csv_invalid_utf8_names_the_file(tmp_path):
    path = tmp_path / "n.csv"
    path.write_bytes(b"from,to,class\na,\xff,register\n")
    with pytest.raises(ValueError, match="n.csv"):
        load_normalise_csv(path)
