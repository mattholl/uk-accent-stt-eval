"""scripts/fetch_english_dialects_samples.py is not a package: load it by path, with its network function faked."""
import importlib.util
import io
import json
import sys
import urllib.parse
import wave
from pathlib import Path

import pytest

from ukstt.cli import main
from ukstt.csvio import read_csv

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_english_dialects_samples.py"
REGIONS = Path(__file__).resolve().parents[1] / "config" / "regions.csv"

# config -> {speaker id: number of rows}; irish has no female subset, midlands_female shares id 7 with the male one
DATA = {
    "irish_male": {1: 5, 2: 5, 3: 5},
    "midlands_male": {7: 6, 8: 4, 9: 4},
    "midlands_female": {7: 5, 5: 2},
    "northern_male": {1: 4}, "scottish_male": {1: 4}, "southern_male": {1: 4}, "welsh_male": {1: 4},
    "northern_female": {1: 3}, "scottish_female": {1: 3}, "southern_female": {1: 3}, "welsh_female": {1: 3},
    "big_male": {1: 130, 2: 90},  # not a real label: only for the paging test
}
SECONDS = {}  # (config, offset) -> duration of that clip, default 0.5


@pytest.fixture
def fetch(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fetch_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table = {cfg: [(spk, f"EN{spk:02d}{i:02d}") for spk, n in speakers.items() for i in range(n)]
             for cfg, speakers in DATA.items()}
    calls = []

    def wav_bytes(seconds):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
            w.writeframes(b"\x01\x00" * int(16000 * seconds))
        return buf.getvalue()

    def fake_get(url, binary=False):
        calls.append(url)
        if url.startswith(mod.API):
            q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
            cfg, off, n = q["config"], int(q["offset"]), int(q["length"])
            assert n <= 100
            rows = [{"row": {"speaker_id": spk, "line_id": line, "text": f"text of {line}",
                             "audio": [{"src": f"http://audio.test/{cfg}/{off + i}.wav"}]}}
                    for i, (spk, line) in enumerate(table[cfg][off:off + n])]
            return {"num_rows_total": len(table[cfg]), "rows": rows}
        cfg, name = url.rsplit("/", 2)[-2:]
        return wav_bytes(SECONDS.get((cfg, int(name[:-4])), 0.5))

    SECONDS.clear()
    monkeypatch.setattr(mod, "get", fake_get)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.chdir(tmp_path)
    mod.calls = calls
    return mod


def clip_ids(path):
    return [r["clip_id"] for r in read_csv(Path(path))]


def test_allocate_round_robin_caps_and_per_speaker(fetch):
    a = fetch.allocate
    assert a([10, 10, 10], 7, None) == [3, 2, 2]  # the first speakers get the extra clip
    assert a([10, 10], 4, None) == [2, 2]
    assert a([10], 4, None) == [4]  # a label with fewer speakers: more clips each
    assert a([1, 5, 5], 9, None) == [1, 4, 4]  # a short speaker is capped, the others take over
    assert a([2, 2], 9, None) == [2, 2]  # not enough rows: what exists
    assert a([4, 1], None, 3) == [3, 1]


def test_list_scans_in_pages_of_100_and_caches(fetch, capsys):
    assert fetch.main(["--list", "--genders", "both"]) == 0
    out = capsys.readouterr().out
    assert "irish_male: 15 rows, 3 speakers: 1 x5, 2 x5, 3 x5" in out
    assert "midlands_male: 14 rows, 3 speakers: 7 x6, 8 x4, 9 x4" in out
    assert "midlands_female: 7 rows, 2 speakers: f7 x5, f5 x2" in out
    assert "irish_female" not in out
    cache = json.loads(Path("data/hf_speakers.json").read_text())
    assert cache["midlands_female"]["rows"] == 7 and len(cache["midlands_female"]["speakers"]["7"]) == 5
    n = len(fetch.calls)
    assert fetch.main(["--list", "--genders", "both"]) == 0  # second time: from the cache
    assert len(fetch.calls) == n
    assert not list(Path("data").glob("audio/*"))  # --list downloads no audio
    assert not any(c.endswith(".wav") for c in fetch.calls)


def test_scan_pages_are_100_rows(fetch):
    out = fetch.scan("big_male")
    assert out["rows"] == 220 and [len(v) for v in out["speakers"].values()] == [130, 90]
    assert len(fetch.calls) == 3  # offsets 0, 100, 200


def test_speakers_cap_and_default_choice_most_rows_then_id(fetch, capsys):
    assert fetch.main(["--speakers", "2", "--clips", "2"]) == 0
    rows = {r["clip_id"]: r for r in read_csv("manifests/clips_in.csv")}
    spk = {r["speaker_id"] for r in rows.values() if r["region"] == "irish"}
    assert spk == {"irish_1", "irish_2"}  # all tie on 5 rows: lowest ids
    spk = {r["speaker_id"] for r in rows.values() if r["region"] == "midlands"}
    assert spk == {"midlands_7", "midlands_8"}  # 7 has most rows, then 8 beats 9 on id
    assert len(rows) == 2 * 2 * 2 + 4 * 1 * 2  # northern etc. have one speaker: min(N, available)
    assert "midlands_f7" not in {r["speaker_id"] for r in rows.values()}  # male by default


def test_clips_per_label_spreads_round_robin_and_warns(fetch, capsys):
    assert fetch.main(["--speakers", "3", "--clips-per-label", "7", "--out", "o.csv"]) == 0
    cap = capsys.readouterr()
    ids = clip_ids("o.csv")
    by = {}
    for r in read_csv("o.csv"):
        by.setdefault(r["region"], {}).setdefault(r["speaker_id"], 0)
        by[r["region"]][r["speaker_id"]] += 1
    assert by["irish"] == {"irish_1": 3, "irish_2": 2, "irish_3": 2}
    assert by["midlands"] == {"midlands_7": 3, "midlands_8": 2, "midlands_9": 2}
    assert by["northern"] == {"northern_1": 4}  # only 4 rows exist
    assert "warning: northern_male: only 4 of 7 clips could be taken" in cap.err
    assert "irish_male: only" not in cap.err
    assert len(ids) == len(set(ids))


def test_clips_and_clips_per_label_are_exclusive(fetch):
    with pytest.raises(SystemExit):
        fetch.main(["--clips", "2", "--clips-per-label", "5"])


def test_female_keys_carry_the_gender_and_irish_is_skipped(fetch):
    assert fetch.main(["--genders", "female", "--speakers", "2", "--clips", "1", "--out", "f.csv"]) == 0
    rows = read_csv("f.csv")
    mid = [r for r in rows if r["region"] == "midlands"]
    assert [r["clip_id"] for r in mid] == ["midlands_f7_en0700", "midlands_f5_en0500"]
    assert {r["source"] for r in mid} == {"ylacombe/english_dialects:midlands_female"}
    assert {r["region"] for r in rows} == {"midlands", "northern", "scottish", "southern", "welsh"}
    assert fetch.main(["--genders", "both", "--speakers", "1", "--clips", "1", "--out", "b.csv"]) == 0
    spk = [r["speaker_id"] for r in read_csv("b.csv")]
    assert "midlands_7" in spk and "midlands_f7" in spk  # same number, no collision
    assert not any(s.startswith("irish_f") for s in spk)
    assert set(clip_ids("b.csv")) >= {"midlands_7_en0700", "midlands_f7_en0700"}


def test_exclude_from_skips_listed_clips_and_other_out_leaves_the_first_alone(fetch):
    assert fetch.main(["--speakers", "1", "--clips", "2"]) == 0
    first = Path("manifests/clips_in.csv").read_bytes()
    old = set(clip_ids("manifests/clips_in.csv"))
    assert fetch.main(["--speakers", "1", "--clips", "2", "--exclude-from", "manifests/clips_in.csv",
                       "--out", "manifests/clips_in_large.csv"]) == 0
    new = set(clip_ids("manifests/clips_in_large.csv"))
    assert new and not (old & new) and len(new) == len(old)
    assert Path("manifests/clips_in.csv").read_bytes() == first
    # repeatable
    assert fetch.main(["--speakers", "1", "--clips", "2", "--exclude-from", "manifests/clips_in.csv",
                       "--exclude-from", "manifests/clips_in_large.csv", "--out", "x.csv"]) == 0
    assert not (set(clip_ids("x.csv")) & (old | new))


def test_existing_wavs_are_not_downloaded_again(fetch):
    assert fetch.main(["--speakers", "1", "--clips", "1", "--out", "a.csv"]) == 0
    audio = [c for c in fetch.calls if c.endswith(".wav")]
    assert len(audio) == 6
    fetch.calls.clear()
    assert fetch.main(["--speakers", "1", "--clips", "1", "--out", "b.csv"]) == 0
    assert not fetch.calls  # cache, wav and reference all present: no request at all


def test_too_long_clip_is_skipped_and_the_next_one_used(fetch):
    SECONDS[("irish_male", 0)] = 20.0
    assert fetch.main(["--speakers", "1", "--clips", "1", "--max-seconds", "12", "--out", "o.csv"]) == 0
    irish = [r for r in read_csv("o.csv") if r["region"] == "irish"]
    assert [r["clip_id"] for r in irish] == ["irish_1_en0101"]
    assert not Path("data/audio/irish_1_en0100.wav").exists()


def test_broken_wav_is_reported_and_deleted(fetch, monkeypatch):
    real = fetch.get
    monkeypatch.setattr(fetch, "get", lambda url, binary=False: b"not a wav" if url.endswith(".wav") else real(url, binary))
    with pytest.raises(SystemExit) as e:
        fetch.main(["--speakers", "1", "--clips", "1"])
    assert "not a readable WAV" in str(e.value)
    assert not list(Path("data/audio").glob("*.wav"))


def test_manifest_written_passes_build_manifest(fetch, capsys):
    assert fetch.main(["--genders", "both", "--speakers", "2", "--clips-per-label", "3", "--out", "m.csv"]) == 0
    capsys.readouterr()
    assert main(["build-manifest", "--in", "m.csv", "--regions", str(REGIONS), "--out", "clips.csv",
                 "--report", "report.csv"]) == 0
    rows = read_csv("clips.csv")
    assert len(rows) == 11 * 3  # six male and five female configs (irish has no female subset)
    assert {r["region"] for r in rows} == {"irish", "midlands", "northern", "scottish", "southern", "welsh"}
    assert all(float(r["duration_s"]) == 0.5 for r in rows)
