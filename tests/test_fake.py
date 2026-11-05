from pathlib import Path

import pytest

from ukstt.normalise import normalise_default
from ukstt.score import align
from ukstt.transcribe.base import ConnectError, HttpError, MalformedResponse, ReadTimeout, validate_response
from ukstt.transcribe.fake import NONSENSE, NO_REFERENCE_TEXT, FakeTranscriber

REF = " ".join(f"apple{'x' * (i % 3)}" for i in range(100))


def fake(rate=0.2, failures=None, ref=REF):
    return FakeTranscriber({"c1": ref}, {"c1": "welsh"}, {"welsh": rate, "unknown": 0.1}, failures)


def test_deterministic_and_shape():
    a = fake().transcribe(Path("x/c1.wav"), {})
    assert a == fake().transcribe(Path("c1.wav"), {})
    assert a["language_code"] == "eng" and a["language_probability"] == 1.0
    assert a["text"][0].isupper() and a["text"].endswith(".")
    assert all(w["type"] == "word" and w["end"] > w["start"] for w in a["words"])
    validate_response(a)


def test_zero_rate_returns_the_reference():
    text = fake(0.0).transcribe(Path("c1.wav"), {})["text"]
    assert text == REF[0].upper() + REF[1:] + "."


def test_no_reference_gets_fixed_text():
    got = fake().transcribe(Path("demo_01.wav"), {})
    assert got["text"] == NO_REFERENCE_TEXT
    assert [w["text"] for w in got["words"]] == ["This", "is", "a", "fake", "transcript"]


def test_nonsense_words_are_letters_only():
    assert all(w.isalpha() and w.islower() for w in NONSENSE)


@pytest.mark.parametrize("token, exc", [("429", HttpError), ("500", HttpError), ("503", HttpError),
                                        ("connect", ConnectError), ("timeout", ReadTimeout)])
def test_failure_tokens_raise_once_per_attempt(token, exc):
    t = fake(failures={"c1": [token, token]})
    for _ in range(2):
        with pytest.raises(exc):
            t.transcribe(Path("c1.wav"), {})
    assert t.transcribe(Path("c1.wav"), {})["text"]


def test_http_failure_details():
    t = fake(failures={"c1": ["429", "503"]})
    with pytest.raises(HttpError) as e429:
        t.transcribe(Path("c1.wav"), {})
    assert (e429.value.status, e429.value.retry_after) == (429, 1.0)
    with pytest.raises(HttpError) as e503:
        t.transcribe(Path("c1.wav"), {})
    assert e503.value.status == 503


def test_empty_and_malformed_tokens():
    t = fake(failures={"c1": ["empty", "malformed"]})
    empty = t.transcribe(Path("c1.wav"), {})
    assert empty["text"] == "" and empty["words"] == []
    validate_response(empty)
    bad = t.transcribe(Path("c1.wav"), {})
    assert bad == {"oops": 1}
    with pytest.raises(MalformedResponse):
        validate_response(bad)


def test_error_rate_is_recovered_on_a_large_sample():
    refs = {f"c{i}": " ".join(f"w{j % 7}" for j in range(100)) for i in range(60)}
    for rate in (0.03, 0.14):
        t = FakeTranscriber(refs, {k: "x" for k in refs}, {"x": rate})
        errors = n_ref = 0
        for clip_id, ref in refs.items():
            hyp = t.transcribe(Path(f"{clip_id}.wav"), {})["text"]
            a = align(normalise_default(ref), normalise_default(hyp))
            errors, n_ref = errors + a.errors, n_ref + a.n_ref
        assert errors / n_ref == pytest.approx(rate, abs=0.02)


def test_from_clips_reads_references_and_regions(clipset):
    path, rows = clipset
    t = FakeTranscriber.from_clips(path, Path("config/fake.toml"))
    assert t.region_of[rows[0]["clip_id"]] == "southern"
    assert t.references[rows[0]["clip_id"]].startswith("word0")


def test_from_clips_rejects_unknown_region(clipset, tmp_path):
    path, _ = clipset
    toml = tmp_path / "f.toml"
    toml.write_text("[error_rates]\nsouthern = 0.1\n")
    with pytest.raises(ValueError, match="irish"):
        FakeTranscriber.from_clips(path, toml)
