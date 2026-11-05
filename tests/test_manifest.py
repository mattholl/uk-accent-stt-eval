import csv
import re
import wave
from pathlib import Path

import pytest

from ukstt.audio import write_test_wav
from ukstt.constants import ID_RE, PILOT_REGIONS
from ukstt.csvio import read_csv, write_csv
from ukstt.dummy import make_dummy_data
from ukstt.manifest import IN_COLUMNS, OUT_COLUMNS, build_manifest, select_stage

REGIONS_CSV = Path("config/regions.csv")


def build(tmp_path, inputs, strict=False):
    return build_manifest(inputs, REGIONS_CSV, tmp_path / "clips.csv", tmp_path / "report.csv", strict=strict)


def codes(issues):
    return sorted(i.code for i in issues)


@pytest.fixture(scope="session")
def dummy(tmp_path_factory):
    """The default dummy set, built once per session. Read-only: write outputs elsewhere."""
    root = tmp_path_factory.mktemp("dummy")
    make_dummy_data(root)
    return root / "manifests"


@pytest.fixture(scope="session")
def clips_csv(dummy):
    """The dummy clips.csv, already validated."""
    issues = build_manifest([dummy / "clips_in.csv"], REGIONS_CSV, dummy / "clips.csv", dummy / "report.csv")
    assert errors(issues) == []
    return dummy / "clips.csv"


class Case:
    """A one-clip pilot-style input that can be tweaked field by field."""

    def __init__(self, tmp_path):
        self.dir = tmp_path
        write_test_wav(tmp_path / "a.wav", 1.0)
        (tmp_path / "a.txt").write_text("hello there\n")
        self.row = {"clip_id": "scottish_01_01", "set": "pilot", "speaker_id": "scottish_01", "region": "scottish",
                    "task": "read", "audio_path": str(tmp_path / "a.wav"),
                    "reference_path": str(tmp_path / "a.txt"), "source": "test", "notes": ""}

    def run(self, extra_rows=(), **changes):
        rows = [{**self.row, **changes}, *extra_rows]
        path = self.dir / "in.csv"
        write_csv(path, rows, IN_COLUMNS)
        return build(self.dir, [path])


@pytest.fixture
def case(tmp_path):
    return Case(tmp_path)


def errors(issues):
    return [i for i in issues if i.level == "error"]


# --- ID_RE -----------------------------------------------------------------

@pytest.mark.parametrize("good", ["scottish_4310", "clip_7", "a", "x" * 64])
def test_id_re_accepts(good):
    assert re.fullmatch(ID_RE, good)


@pytest.mark.parametrize("bad", ["has space", "Upper", "a/b", "", "x" * 65, "a\n", "dash-ed"])
def test_id_re_rejects(bad):
    assert not re.fullmatch(ID_RE, bad)


# --- dummy data --------------------------------------------------------------

def test_dummy_layout(dummy):
    rows = read_csv(dummy / "clips_in.csv")
    assert list(rows[0]) == list(IN_COLUMNS)
    pilot = [r for r in rows if r["set"] == "pilot"]
    assert len(pilot) == 6 * 4 and len(rows) == 27
    assert {r["region"] for r in pilot} == set(PILOT_REGIONS)
    assert {r["task"] for r in pilot} == {"read"}
    first = pilot[0]
    assert first["clip_id"] == "southern_01_01" and first["speaker_id"] == "southern_01"
    assert {r["clip_id"] for r in rows if r["set"] == "demo"} == {"demo_01", "demo_02", "demo_03"}
    demo = [r for r in rows if r["set"] == "demo"]
    assert all(r["region"] == r["task"] == "unknown" and r["reference_path"] == "" for r in demo)
    assert all(r["speaker_id"] == r["clip_id"] for r in demo)
    assert len(list((dummy.parent / "recordings").glob("*.wav"))) == 27
    assert len(list((dummy.parent / "references").glob("*.txt"))) == 24


def test_dummy_reference_has_requested_word_count(tmp_path):
    make_dummy_data(tmp_path, words=7, seconds=0.5)
    words = (tmp_path / "references" / "irish_02_02.txt").read_text().split()
    assert len(words) == 7 and all(w.isalpha() and w.islower() for w in words)


def test_dummy_is_deterministic_and_clips_differ(tmp_path):
    make_dummy_data(tmp_path / "a", seconds=1)
    make_dummy_data(tmp_path / "b", seconds=1)
    names = sorted(p.name for p in (tmp_path / "a" / "recordings").glob("*.wav"))
    for name in names:
        assert (tmp_path / "a" / "recordings" / name).read_bytes() == (tmp_path / "b" / "recordings" / name).read_bytes()
    assert len({(tmp_path / "a" / "recordings" / n).read_bytes() for n in names}) == len(names)
    ref = (tmp_path / "a" / "references" / "welsh_01_01.txt").read_text()
    assert ref == (tmp_path / "b" / "references" / "welsh_01_01.txt").read_text()
    make_dummy_data(tmp_path / "c", seconds=1, seed=1)
    assert ref != (tmp_path / "c" / "references" / "welsh_01_01.txt").read_text()


def test_dummy_speaker_spread(tmp_path):
    make_dummy_data(tmp_path, clips_per_region=5, speakers_per_region=2, seconds=0.5)
    ids = [r["clip_id"] for r in read_csv(tmp_path / "manifests" / "clips_in.csv") if r["region"] == "welsh"]
    assert ids == ["welsh_01_01", "welsh_02_01", "welsh_01_02", "welsh_02_02", "welsh_01_03"]


def test_dummy_rejects_zero_counts(tmp_path):
    with pytest.raises(ValueError):
        make_dummy_data(tmp_path, clips_per_region=0)


# --- build_manifest on dummy data ---------------------------------------------

def test_dummy_builds_without_errors_or_warnings(dummy, tmp_path):
    issues = build(tmp_path, [dummy / "clips_in.csv"])
    assert issues == []  # demo clips are single-clip speakers by design: no warning
    rows = read_csv(tmp_path / "clips.csv")
    assert list(rows[0]) == list(OUT_COLUMNS) and len(rows) == 27
    first = rows[0]
    assert len(first["audio_sha256"]) == 64 and first["duration_s"] == "20.000000"
    assert (first["sample_rate_hz"], first["channels"]) == ("16000", "1")
    assert len({r["audio_sha256"] for r in rows}) == 27


def test_report_csv_written_with_header_even_when_clean(case):
    case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])
    assert (case.dir / "report.csv").read_text().splitlines() == ["level,code,path,message"]


def test_report_csv_lists_issues_and_clips_csv_withheld(case):
    issues = case.run(region="atlantis")
    assert codes(issues) == ["E_REGION_UNKNOWN", "W_SINGLE_CLIP_SPEAKER"]
    with open(case.dir / "report.csv", newline="") as fh:
        report = list(csv.DictReader(fh))
    assert [r["code"] for r in report] == ["E_REGION_UNKNOWN", "W_SINGLE_CLIP_SPEAKER"]
    assert report[0]["level"] == "error" and report[0]["path"] == "scottish_01_01"
    assert not (case.dir / "clips.csv").exists()


def test_inputs_are_concatenated_in_order(dummy, tmp_path):
    rows = read_csv(dummy / "clips_in.csv")
    write_csv(tmp_path / "one.csv", rows[:3], IN_COLUMNS)
    write_csv(tmp_path / "two.csv", rows[3:6], IN_COLUMNS)
    build(tmp_path, [tmp_path / "two.csv", tmp_path / "one.csv"])
    got = [r["clip_id"] for r in read_csv(tmp_path / "clips.csv")]
    assert got == [r["clip_id"] for r in rows[3:6] + rows[:3]]


def test_missing_column_is_value_error(tmp_path):
    (tmp_path / "bad.csv").write_text("clip_id,set\nx,pilot\n")
    with pytest.raises(ValueError, match="missing column"):
        build(tmp_path, [tmp_path / "bad.csv"])


def test_crlf_input_is_accepted(case):
    case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])
    path = case.dir / "in.csv"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert errors(build(case.dir, [path])) == []


# --- one negative case per error code ----------------------------------------

def test_clean_single_case_only_warns_about_single_clip(case):
    assert codes(case.run()) == ["W_SINGLE_CLIP_SPEAKER"]


def test_e_audio_format_sample_rate(case):
    write_test_wav(case.dir / "a.wav", 1.0, sample_rate_hz=8000)
    issues = case.run()
    assert "E_AUDIO_FORMAT" in codes(issues)
    assert "ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav" in next(i for i in issues if i.code == "E_AUDIO_FORMAT").message


def test_e_audio_format_stereo(case):
    with wave.open(str(case.dir / "a.wav"), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x01\x00" * 2 * 16000)
    assert "E_AUDIO_FORMAT" in codes(case.run())


def test_e_audio_format_8_bit(case):
    with wave.open(str(case.dir / "a.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)
        wf.setframerate(16000)
        wf.writeframes(b"\x80" * 16000)
    assert "E_AUDIO_FORMAT" in codes(case.run())


def test_e_audio_format_not_a_wav(case):
    (case.dir / "a.wav").write_bytes(b"this is not audio")
    assert "E_AUDIO_FORMAT" in codes(case.run())


def test_e_audio_missing(case):
    assert "E_AUDIO_MISSING" in codes(case.run(audio_path=str(case.dir / "nope.wav")))
    assert "E_AUDIO_MISSING" in codes(case.run(audio_path=""))


def test_e_audio_too_short(case):
    write_test_wav(case.dir / "a.wav", 0.05)
    assert "E_AUDIO_TOO_SHORT" in codes(case.run())


def test_e_ref_missing_pilot(case):
    assert "E_REF_MISSING" in codes(case.run(reference_path=""))
    assert "E_REF_MISSING" in codes(case.run(reference_path=str(case.dir / "nope.txt")))


def test_e_ref_empty_after_norm(case):
    (case.dir / "a.txt").write_text("um [unclear] (laughs)\n")
    assert "E_REF_EMPTY_AFTER_NORM" in codes(case.run())


def test_e_region_unknown(case):
    assert "E_REGION_UNKNOWN" in codes(case.run(region="atlantis"))


def test_e_region_unknown_literal_on_pilot(case):
    assert "E_REGION_UNKNOWN" in codes(case.run(region="unknown"))


def test_e_task_bad(case):
    assert "E_TASK_BAD" in codes(case.run(task="shouting"))
    assert "E_TASK_BAD" in codes(case.run(task="unknown"))  # pilot clips need read or spont
    assert "E_TASK_BAD" not in codes(case.run(task="spont"))


def test_e_id_bad(case):
    assert "E_ID_BAD" in codes(case.run(clip_id="Has Space"))
    assert "E_ID_BAD" in codes(case.run(speaker_id="a/b"))
    assert "E_ID_BAD" in codes(case.run(clip_id=""))


def test_e_dup_clip(case):
    assert codes(case.run(extra_rows=[case.row])).count("E_DUP_CLIP") == 1


def test_e_dup_clip_across_input_files(case):
    write_csv(case.dir / "one.csv", [case.row], IN_COLUMNS)
    issues = build(case.dir, [case.dir / "one.csv", case.dir / "one.csv"])
    assert "E_DUP_CLIP" in codes(issues)


def test_e_set_bad(case):
    assert "E_SET_BAD" in codes(case.run(set="test"))


# --- warnings ----------------------------------------------------------------

def test_w_ref_digits_and_brackets_are_warnings_not_errors(case):
    (case.dir / "a.txt").write_text("it cost 5 pounds [laughs]\n")
    issues = case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])
    assert errors(issues) == []
    assert {"W_REF_DIGITS", "W_REF_BRACKET"} <= set(codes(issues))
    assert (case.dir / "clips.csv").exists()


def test_w_duration_over_60_s(case):
    write_test_wav(case.dir / "a.wav", 61.0)
    issues = case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])
    assert codes(issues).count("W_DURATION") == 2 and errors(issues) == []


def test_w_single_clip_speaker(case):
    assert codes(case.run()) == ["W_SINGLE_CLIP_SPEAKER"]
    assert codes(case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])) == []


def test_strict_turns_warnings_into_errors(case):
    path = case.dir / "in.csv"
    write_csv(path, [case.row], IN_COLUMNS)
    issues = build(case.dir, [path], strict=True)
    assert [(i.level, i.code) for i in issues] == [("error", "W_SINGLE_CLIP_SPEAKER")]
    assert not (case.dir / "clips.csv").exists()


# --- demo clips ----------------------------------------------------------------

def test_demo_clip_without_reference_builds(case):
    issues = case.run(set="demo", region="unknown", task="unknown", reference_path="")
    assert errors(issues) == []
    assert read_csv(case.dir / "clips.csv")[0]["reference_path"] == ""


def test_demo_clip_with_reference_builds(case):
    assert errors(case.run(set="demo", region="unknown", task="unknown")) == []


def test_demo_clip_unlisted_region_is_still_an_error(case):
    assert "E_REGION_UNKNOWN" in codes(case.run(set="demo", region="atlantis", task="unknown"))


# --- select ------------------------------------------------------------------------

def test_select_pilot_returns_every_pilot_region_clip(clips_csv, tmp_path):
    out = tmp_path / "pilot.csv"
    rows = select_stage(clips_csv, "pilot", out)
    assert len(rows) == 24 and {r["set"] for r in rows} == {"pilot"}
    assert {r["region"] for r in rows} == set(PILOT_REGIONS)
    assert [r["clip_id"] for r in rows] == sorted(r["clip_id"] for r in rows)
    assert sum(float(r["duration_s"]) for r in rows) / 60 < 10.0
    assert read_csv(out) == rows


def test_select_demo_returns_only_demo_rows(clips_csv, tmp_path):
    rows = select_stage(clips_csv, "demo", tmp_path / "demo.csv")
    assert [r["clip_id"] for r in rows] == ["demo_01", "demo_02", "demo_03"]


def test_select_smoke_is_first_southern_pilot_clip(clips_csv, tmp_path):
    rows = select_stage(clips_csv, "smoke", tmp_path / "smoke.csv")
    assert [r["clip_id"] for r in rows] == ["southern_01_01"]
    assert rows[0]["region"] == "southern" and rows[0]["set"] == "pilot"


def fake_clips(path, specs):
    """specs: (clip_id, set, region, seconds)."""
    rows = [{**dict.fromkeys(OUT_COLUMNS, ""), "clip_id": c, "set": s, "speaker_id": c, "region": r,
             "duration_s": f"{sec:.6f}"} for c, s, r, sec in specs]
    write_csv(path, rows, OUT_COLUMNS)


def six_regions(seconds):
    return [(f"{r}_1", "pilot", r, seconds) for r in PILOT_REGIONS]


def test_select_pilot_cap(tmp_path):
    fake_clips(tmp_path / "c.csv", six_regions(100.0))  # 600 s = exactly 10.0 min: allowed
    assert len(select_stage(tmp_path / "c.csv", "pilot", tmp_path / "p.csv")) == 6
    fake_clips(tmp_path / "c.csv", six_regions(100.1))  # 600.6 s
    with pytest.raises(ValueError, match="cap"):
        select_stage(tmp_path / "c.csv", "pilot", tmp_path / "p.csv")
    assert len(read_csv(tmp_path / "p.csv")) == 6  # still the earlier file: a refused stage writes nothing


def test_select_pilot_region_without_clips(tmp_path):
    fake_clips(tmp_path / "c.csv", six_regions(10.0)[:-1])
    with pytest.raises(ValueError, match="irish"):
        select_stage(tmp_path / "c.csv", "pilot", tmp_path / "p.csv")


def test_select_pilot_ignores_demo_and_non_pilot_regions(tmp_path):
    fake_clips(tmp_path / "c.csv", six_regions(10.0) + [("demo_1", "demo", "unknown", 500.0)])
    assert len(select_stage(tmp_path / "c.csv", "pilot", tmp_path / "p.csv")) == 6


def test_select_demo_cap_and_empty(tmp_path):
    fake_clips(tmp_path / "c.csv", six_regions(10.0))
    with pytest.raises(ValueError, match="no demo"):
        select_stage(tmp_path / "c.csv", "demo", tmp_path / "d.csv")
    fake_clips(tmp_path / "c.csv", [("d1", "demo", "unknown", 90.0), ("d2", "demo", "unknown", 90.1)])
    with pytest.raises(ValueError, match="cap"):
        select_stage(tmp_path / "c.csv", "demo", tmp_path / "d.csv")
    fake_clips(tmp_path / "c.csv", [("d1", "demo", "unknown", 90.0), ("d2", "demo", "unknown", 90.0)])
    assert len(select_stage(tmp_path / "c.csv", "demo", tmp_path / "d.csv")) == 2


def test_select_smoke_without_southern_and_unknown_stage(tmp_path):
    fake_clips(tmp_path / "c.csv", [("m1", "pilot", "midlands", 5.0)])
    with pytest.raises(ValueError, match="southern"):
        select_stage(tmp_path / "c.csv", "smoke", tmp_path / "s.csv")
    with pytest.raises(ValueError, match="stage"):
        select_stage(tmp_path / "c.csv", "full", tmp_path / "s.csv")


def test_select_sorts_by_clip_id(tmp_path):
    specs = six_regions(10.0)
    fake_clips(tmp_path / "c.csv", [("southern_9", "pilot", "southern", 5.0)] + specs)
    rows = select_stage(tmp_path / "c.csv", "smoke", tmp_path / "s.csv")
    assert rows[0]["clip_id"] == "southern_1"


def test_select_ignores_demo_clip_that_sorts_first(tmp_path):
    fake_clips(tmp_path / "c.csv", [("a_demo", "demo", "southern", 5.0)] + six_regions(10.0))
    for stage, n in (("smoke", 1), ("pilot", 6)):
        rows = select_stage(tmp_path / "c.csv", stage, tmp_path / "s.csv")
        assert len(rows) == n and "a_demo" not in {r["clip_id"] for r in rows}


def test_select_needs_the_clips_csv_columns(tmp_path):
    write_csv(tmp_path / "c.csv", [{"clip_id": "a", "set": "pilot", "region": "southern"}], ["clip_id", "set", "region"])
    with pytest.raises(ValueError, match="duration_s"):
        select_stage(tmp_path / "c.csv", "smoke", tmp_path / "s.csv")
    assert not (tmp_path / "s.csv").exists()


# --- review fixes R10-R14 ------------------------------------------------------------

def test_regions_file_needs_region_id(case):
    write_csv(case.dir / "bad_regions.csv", [{"name": "x"}], ["name"])
    write_csv(case.dir / "in.csv", [case.row], IN_COLUMNS)
    with pytest.raises(ValueError, match="region_id"):
        build_manifest([case.dir / "in.csv"], case.dir / "bad_regions.csv", case.dir / "c.csv", case.dir / "r.csv")


@pytest.mark.parametrize("content", ["", "clip_id,set\n", ",".join(IN_COLUMNS) + "\n"])
def test_empty_input_is_value_error_and_keeps_clips_csv(case, content):
    (case.dir / "clips.csv").write_text("keep\n")
    (case.dir / "empty.csv").write_text(content)
    with pytest.raises(ValueError, match="no clip rows"):
        build(case.dir, [case.dir / "empty.csv"])
    assert (case.dir / "clips.csv").read_text() == "keep\n"


def test_errors_delete_stale_clips_csv(case):
    case.run(extra_rows=[{**case.row, "clip_id": "scottish_01_02"}])
    assert (case.dir / "clips.csv").exists()
    case.run(region="atlantis")
    assert not (case.dir / "clips.csv").exists()


def test_truncated_wav_is_audio_format_error(case):
    path = case.dir / "a.wav"
    path.write_bytes(path.read_bytes()[:20000])  # header still says 1 s (32044 bytes)
    issues = case.run()
    assert "E_AUDIO_FORMAT" in codes(issues)
    assert "truncated" in next(i for i in issues if i.code == "E_AUDIO_FORMAT").message


def test_demo_clip_gets_no_single_clip_warning(case):
    assert codes(case.run(set="demo", region="unknown", task="unknown")) == []


def test_dummy_rejects_bad_seconds(tmp_path):
    for bad in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="seconds"):
            make_dummy_data(tmp_path, seconds=bad)
