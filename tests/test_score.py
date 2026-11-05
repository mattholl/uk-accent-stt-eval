import random

import pytest

from ukstt.score import Alignment, align


def words(s):
    return s.split()


def test_identical():
    a = align(words("the cat sat"), words("the cat sat"))
    assert (a.hits, a.subs, a.dels, a.ins, a.errors, a.wer) == (3, 0, 0, 0, 0, 0.0)
    assert a.ops == (("H", "the", "the"), ("H", "cat", "cat"), ("H", "sat", "sat"))


def test_one_substitution():
    a = align(words("the cat sat"), words("the dog sat"))
    assert (a.subs, a.dels, a.ins) == (1, 0, 0)
    assert a.wer == pytest.approx(1 / 3)
    assert a.ops[1] == ("S", "cat", "dog")


def test_deletions():
    a = align(words("the cat sat on the mat"), words("the cat sat"))
    assert (a.n_ref, a.n_hyp, a.hits, a.subs, a.dels, a.ins) == (6, 3, 3, 0, 3, 0)
    assert a.wer == 0.5


def test_insertions_are_not_clipped():
    a = align(words("hello"), words("hello there you"))
    assert (a.hits, a.subs, a.dels, a.ins) == (1, 0, 0, 2)
    assert a.wer == 2.0
    assert a.ops == (("H", "hello", "hello"), ("I", None, "there"), ("I", None, "you"))


def test_empty_hypothesis():
    a = align(words("a b c"), [])
    assert (a.dels, a.errors, a.wer) == (3, 3, 1.0)
    assert a.ops == (("D", "a", None), ("D", "b", None), ("D", "c", None))


def test_empty_reference_has_no_wer():
    assert align([], []).wer is None
    a = align([], words("a b"))
    assert (a.n_ref, a.ins, a.errors, a.wer) == (0, 2, 2, None)


def test_alignment_is_frozen_and_ops_is_a_tuple():
    a = align(["a"], ["b"])
    assert isinstance(a, Alignment) and isinstance(a.ops, tuple)
    with pytest.raises(AttributeError):
        a.subs = 5  # type: ignore[misc]


def test_tie_break_prefers_substitution():
    a = align(words("a b"), words("b a"))
    assert (a.subs, a.dels, a.ins) == (2, 0, 0)
    assert a.ops == (("S", "a", "b"), ("S", "b", "a"))


def test_tie_break_deletion_then_insertion():
    a = align(words("a b c"), words("b c d"))
    assert (a.hits, a.subs, a.dels, a.ins) == (2, 0, 1, 1)
    assert a.ops == (("D", "a", None), ("H", "b", "b"), ("H", "c", "c"), ("I", None, "d"))


def edit_distance(ref, hyp):
    """Independent Levenshtein distance (two rows, no backtrace)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j - 1] + (r != h), prev[j] + 1, cur[j - 1] + 1))
        prev = cur
    return prev[-1]


def test_random_property_against_independent_edit_distance():
    rng = random.Random(20261102)
    for _ in range(500):
        ref = [rng.choice("abcd") for _ in range(rng.randint(0, 9))]
        hyp = [rng.choice("abcd") for _ in range(rng.randint(0, 9))]
        a = align(ref, hyp)
        assert a.errors == a.subs + a.dels + a.ins == edit_distance(ref, hyp)
        assert a.hits + a.subs + a.dels == a.n_ref == len(ref)
        assert a.hits + a.subs + a.ins == a.n_hyp == len(hyp)
        assert [r for k, r, h in a.ops if k != "I"] == ref
        assert [h for k, r, h in a.ops if k != "D"] == hyp
        assert all((r == h) == (k == "H") for k, r, h in a.ops if k in "HS")
        assert a.wer == (a.errors / len(ref) if ref else None)
