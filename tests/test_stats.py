import pytest

from ukstt.constants import MIN_SPEAKERS_CI
from ukstt.stats import SpeakerCounts, bootstrap_ci, percentile_interval, pooled_wer


def speakers(errors, n_ref):
    return [SpeakerCounts(f"s{i}", e, n) for i, (e, n) in enumerate(zip(errors, n_ref))]


MIXED = speakers([1, 3, 5, 2, 8, 4], [10, 10, 20, 10, 25, 12])


def test_pooled_wer_is_micro_average():
    assert pooled_wer(speakers([1, 3], [10, 10])) == pytest.approx(0.2)
    assert pooled_wer(speakers([0, 9], [90, 10])) == pytest.approx(0.09)  # not the mean of 0.0 and 0.9


def test_pooled_wer_without_words_raises():
    with pytest.raises(ValueError):
        pooled_wer([])


def test_percentile_interval_controlled():
    assert percentile_interval(list(range(10_000))) == (250, 9749)
    assert percentile_interval(list(range(100)), alpha=0.1) == (5, 94)
    with pytest.raises(ValueError):
        percentile_interval([])


def test_fewer_than_five_speakers_gives_none():
    assert MIN_SPEAKERS_CI == 5
    assert bootstrap_ci([], "read|welsh") is None
    assert bootstrap_ci(MIXED[:4], "read|welsh") is None
    assert bootstrap_ci(MIXED[:5], "read|welsh", B=200) is not None


def test_identical_speakers_give_a_zero_width_interval():
    lo, hi = bootstrap_ci(speakers([1] * 5, [10] * 5), "read|southern", B=500)
    assert lo == hi == pytest.approx(0.1)


def test_deterministic_per_key():
    first = bootstrap_ci(MIXED, "read|welsh", B=2000)
    assert first == bootstrap_ci(MIXED, "read|welsh", B=2000)
    assert first != bootstrap_ci(MIXED, "read|irish", B=2000)
    assert first != bootstrap_ci(MIXED, "read|welsh", B=2000, seed=1)


def test_interval_is_ordered_and_within_speaker_range():
    lo, hi = bootstrap_ci(MIXED, "read|welsh")
    rates = [s.errors / s.n_ref for s in MIXED]
    assert min(rates) <= lo <= hi <= max(rates)


def test_zero_word_speakers_are_dropped_before_the_minimum_check():
    padded = MIXED[:4] + [SpeakerCounts("z1", 0, 0), SpeakerCounts("z2", 3, 0)]
    assert bootstrap_ci(padded, "read|welsh", B=200) is None
    more = MIXED[:5] + [SpeakerCounts("z1", 0, 0)]
    assert bootstrap_ci(more, "read|welsh", B=200) == bootstrap_ci(MIXED[:5], "read|welsh", B=200)


@pytest.mark.parametrize("bad", [SpeakerCounts("x", 1, -1), SpeakerCounts("x", -1, 10)])
def test_negative_counts_raise(bad):
    with pytest.raises(ValueError):
        bootstrap_ci(MIXED + [bad], "read|welsh", B=200)


def test_input_order_does_not_change_the_interval():
    assert bootstrap_ci(MIXED, "read|welsh", B=2000) == bootstrap_ci(MIXED[::-1], "read|welsh", B=2000)
