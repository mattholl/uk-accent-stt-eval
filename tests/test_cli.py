from pathlib import Path

import pytest

from ukstt.cli import main
from ukstt.csvio import read_csv, write_csv


def make(tmp_path, seconds="1"):
    out = tmp_path / "dummy"
    assert main(["make-dummy-data", "--out", str(out), "--seconds", seconds]) == 0
    return out / "manifests"


def build_args(m):
    return ["build-manifest", "--in", str(m / "clips_in.csv"), "--out", str(m / "clips.csv"),
            "--report", str(m / "validation_report.csv"), "--regions", "config/regions.csv"]


def test_dummy_build_select_pipeline(tmp_path, capsys):
    m = make(tmp_path)
    assert (m / "clips_in.csv").exists()
    assert main(build_args(m)) == 0
    assert (m / "validation_report.csv").exists()
    assert "27 clips, 6 regions, 15 speakers" in capsys.readouterr().out
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot"]) == 0
    assert len(read_csv(m / "pilot.csv")) == 24
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "smoke"]) == 0
    assert [r["clip_id"] for r in read_csv(m / "smoke.csv")] == ["southern_01_01"]
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "demo", "--out", str(tmp_path / "d.csv")]) == 0
    assert len(read_csv(tmp_path / "d.csv")) == 3


def test_make_dummy_data_flags(tmp_path):
    out = tmp_path / "x"
    assert main(["make-dummy-data", "--out", str(out), "--clips-per-region", "2", "--speakers-per-region", "1",
                 "--seconds", "0.5", "--seed", "7"]) == 0
    rows = read_csv(out / "manifests" / "clips_in.csv")
    assert len(rows) == 6 * 2 + 3
    assert main(["make-dummy-data", "--out", str(out), "--clips-per-region", "0"]) == 2


def test_build_manifest_exit_2_on_error_and_no_clips_csv(tmp_path, capsys):
    m = make(tmp_path)
    (tmp_path / "dummy" / "recordings" / "welsh_01_01.wav").unlink()
    assert main(build_args(m)) == 2
    assert not (m / "clips.csv").exists()
    assert "E_AUDIO_MISSING" in (m / "validation_report.csv").read_text()
    assert "E_AUDIO_MISSING" in capsys.readouterr().err


def test_build_manifest_strict_exit_2_on_warning(tmp_path):
    m = make(tmp_path)
    (tmp_path / "dummy" / "references" / "welsh_01_01.txt").write_text("it cost 5 pounds\n")
    assert main(build_args(m) + ["--strict"]) == 2  # W_REF_DIGITS becomes an error
    assert main(build_args(m)) == 0


def test_build_manifest_bad_input_file_exits_2(tmp_path, capsys):
    assert main(["build-manifest", "--in", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "c.csv"),
                 "--report", str(tmp_path / "r.csv")]) == 2
    assert "error" in capsys.readouterr().err


def test_select_cap_failure_exits_2(tmp_path, capsys):
    m = make(tmp_path)
    assert main(build_args(m)) == 0
    rows = read_csv(m / "clips.csv")
    for r in rows:
        r["duration_s"] = "30.000000"  # 24 x 30 s = 12 min
    write_csv(m / "clips.csv", rows, list(rows[0]))
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot"]) == 2
    assert "cap" in capsys.readouterr().err
    assert not (m / "pilot.csv").exists()


def test_select_default_out_is_next_to_clips(tmp_path):
    m = make(tmp_path)
    main(build_args(m))
    main(["select", "--clips", str(m / "clips.csv"), "--stage", "demo"])
    assert (m / "demo.csv").exists()


def test_default_inputs_with_and_without_demo_in(tmp_path, monkeypatch, capsys):
    m = make(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifests").mkdir()
    rows = read_csv(m / "clips_in.csv")
    write_csv(tmp_path / "manifests" / "clips_in.csv", rows[:24], list(rows[0]))
    regions = Path(__file__).parent.parent / "config" / "regions.csv"
    assert main(["build-manifest", "--regions", str(regions)]) == 0
    assert len(read_csv("manifests/clips.csv")) == 24
    write_csv(tmp_path / "manifests" / "demo_in.csv", rows[24:], list(rows[0]))
    assert main(["build-manifest", "--regions", str(regions)]) == 0
    assert len(read_csv("manifests/clips.csv")) == 27
    assert "27 clips, 6 regions" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    ["select", "--stage", "smoke", "--clips", "{clips_in}"],
    ["build-manifest", "--regions", "{clips_in}", "--in", "{clips_in}"],
    ["make-dummy-data", "--out", "{clips_in}"],
    ["make-dummy-data", "--out", "{tmp}/d", "--seconds", "-1"],
])
def test_user_errors_exit_2_with_one_line(tmp_path, capsys, argv):
    m = make(tmp_path)
    capsys.readouterr()
    sub = {"clips_in": str(m / "clips_in.csv"), "tmp": str(tmp_path)}
    assert main([a.format(**sub) for a in argv]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and len(err.splitlines()) == 1


def _long_pilot(tmp_path, seconds="30.000000"):
    m = make(tmp_path)
    assert main(build_args(m)) == 0
    rows = read_csv(m / "clips.csv")
    for r in rows:
        r["duration_s"] = seconds  # 24 clips
    write_csv(m / "clips.csv", rows, list(rows[0]))
    return m


def test_select_cap_minutes_overrides_the_pilot_cap(tmp_path, capsys):
    m = _long_pilot(tmp_path)  # 12 min
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot"]) == 2
    assert "--cap-minutes" in capsys.readouterr().err  # the refusal names the flag
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot", "--cap-minutes", "12"]) == 0
    assert len(read_csv(m / "pilot.csv")) == 24
    (m / "pilot.csv").unlink()
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot", "--cap-minutes", "11.9"]) == 2
    assert "11.9 min cap" in capsys.readouterr().err and not (m / "pilot.csv").exists()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_select_cap_minutes_must_be_finite_and_positive(tmp_path, capsys, value):
    m = _long_pilot(tmp_path, "1.000000")
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot", "--cap-minutes", value]) == 2
    assert "--cap-minutes must be a finite number above 0" in capsys.readouterr().err


@pytest.mark.parametrize("stage", ["smoke", "demo"])
def test_select_cap_minutes_is_for_the_pilot_only(tmp_path, capsys, stage):
    m = _long_pilot(tmp_path, "1.000000")
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", stage, "--cap-minutes", "50"]) == 2
    assert "pilot only" in capsys.readouterr().err
