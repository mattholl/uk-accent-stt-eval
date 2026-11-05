import hashlib
import wave

import pytest

from ukstt.audio import WavInfo, probe_wav, sha256_file, write_test_wav
from ukstt.csvio import fmt_float, read_csv, write_csv


def test_write_test_wav_round_trip(tmp_path):
    path = tmp_path / "sub" / "a.wav"
    write_test_wav(path, 1.5, sample_rate_hz=16000, seed=3)
    assert probe_wav(path) == WavInfo(16000, 1, 2, 24000, 1.5)


def test_probe_other_rate(tmp_path):
    write_test_wav(tmp_path / "a.wav", 0.25, sample_rate_hz=48000)
    info = probe_wav(tmp_path / "a.wav")
    assert (info.sample_rate_hz, info.n_frames, info.duration_s) == (48000, 12000, 0.25)


def test_probe_reports_stereo_and_width(tmp_path):
    with wave.open(str(tmp_path / "s.wav"), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(1)
        wf.setframerate(8000)
        wf.writeframes(b"\x80" * 2 * 800)
    info = probe_wav(tmp_path / "s.wav")
    assert (info.channels, info.sampwidth_bytes, info.sample_rate_hz, info.duration_s) == (2, 1, 8000, 0.1)


@pytest.mark.parametrize("content", [b"", b"not a wav at all", b"RIFF\x00\x00\x00\x00WAVE"])
def test_probe_garbage_is_value_error(tmp_path, content):
    (tmp_path / "x.wav").write_bytes(content)
    with pytest.raises(ValueError):
        probe_wav(tmp_path / "x.wav")


def test_probe_missing_file_is_os_error(tmp_path):
    with pytest.raises(OSError):
        probe_wav(tmp_path / "nope.wav")


def test_write_test_wav_is_seeded_and_quiet(tmp_path):
    write_test_wav(tmp_path / "a.wav", 0.5, seed=1)
    write_test_wav(tmp_path / "b.wav", 0.5, seed=1)
    write_test_wav(tmp_path / "c.wav", 0.5, seed=2)
    a, b, c = (sha256_file(tmp_path / f"{n}.wav") for n in "abc")
    assert a == b != c
    with wave.open(str(tmp_path / "a.wav")) as wf:
        data = wf.readframes(wf.getnframes())
    samples = [int.from_bytes(data[i:i + 2], "little", signed=True) for i in range(0, len(data), 2)]
    assert max(map(abs, samples)) <= 500 and any(samples)


def test_sha256_matches_hashlib(tmp_path):
    payload = b"abc" * 1_000_000  # larger than one read block
    (tmp_path / "f.bin").write_bytes(payload)
    assert sha256_file(tmp_path / "f.bin") == hashlib.sha256(payload).hexdigest()
    (tmp_path / "e.bin").write_bytes(b"")
    assert sha256_file(tmp_path / "e.bin") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_fmt_float():
    assert fmt_float(None) == "" and fmt_float(float("nan")) == ""
    assert fmt_float(0.5) == "0.500000" and fmt_float(2.0) == "2.000000"


def test_csv_round_trip_lf_and_atomic(tmp_path):
    rows = [{"a": "1", "b": "x,y"}, {"a": "é", "b": 'say "hi"'}]
    write_csv(tmp_path / "d" / "t.csv", rows, ["a", "b"])
    raw = (tmp_path / "d" / "t.csv").read_bytes()
    assert b"\r" not in raw and raw.startswith(b"a,b\n")
    assert read_csv(tmp_path / "d" / "t.csv") == rows
    assert [p.name for p in (tmp_path / "d").iterdir()] == ["t.csv"]  # no temp file left


def test_read_csv_accepts_crlf_and_bom(tmp_path):
    (tmp_path / "w.csv").write_bytes(b"\xef\xbb\xbfa,b\r\n1,2\r\n")
    assert read_csv(tmp_path / "w.csv") == [{"a": "1", "b": "2"}]
