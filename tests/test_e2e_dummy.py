import tomllib

from ukstt.cli import main
from ukstt.csvio import read_csv
from ukstt.dummy import make_dummy_data

CSVS = ("utterance_scores", "speaker_scores", "region_summary", "pairwise_vs_baseline", "error_pairs")


def write_config(tmp_path, name):
    cfg = tmp_path / f"{name}.toml"
    cfg.write_text(f'[paths]\nruns_dir = "{tmp_path / name / "runs"}"\nresults_dir = "{tmp_path / name / "results"}"\n')
    return cfg


def pipeline(tmp_path, name, **dummy_args):
    """make-dummy-data, build-manifest, select, transcribe (fake), score, stats; returns the results dir."""
    dummy, m = tmp_path / "dummy", tmp_path / "dummy" / "manifests"
    if not dummy.exists():
        make_dummy_data(dummy, **dummy_args)
        assert main(["build-manifest", "--in", str(m / "clips_in.csv"), "--out", str(m / "clips.csv"),
                     "--report", str(m / "validation_report.csv")]) == 0
        assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot"]) == 0
        assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "demo"]) == 0
    cfg = write_config(tmp_path, name)
    for stage in ("pilot", "demo"):
        assert main(["--config", str(cfg), "transcribe", "--clips", str(m / f"{stage}.csv"),
                     "--run-id", f"dummy-{stage}-001"]) == 0
        assert main(["--config", str(cfg), "score", "--run-id", f"dummy-{stage}-001"]) == 0
        assert main(["--config", str(cfg), "stats", "--run-id", f"dummy-{stage}-001"]) == 0
    return tmp_path / name / "results" / "dummy-pilot-001"


def test_default_dummy_set_has_low_n_and_no_cis(tmp_path):
    out = pipeline(tmp_path, "a", seconds=0.5)
    for name in CSVS:
        assert (out / f"{name}.csv").exists()
    summary = read_csv(out / "region_summary.csv")
    assert len(summary) == 6
    assert all(r["low_n"] == "true" and r["ci_lo"] == "" and r["ci_hi"] == "" for r in summary)
    assert all(r["low_n"] == "true" for r in read_csv(out / "pairwise_vs_baseline.csv"))
    assert len(read_csv(out / "pairwise_vs_baseline.csv")) == 5
    # the demo set has no references: transcribed but never scored
    demo = read_csv(tmp_path / "a" / "results" / "dummy-demo-001" / "utterance_scores.csv")
    assert [r["status"] for r in demo] == ["no_reference"] * 3


def test_two_runs_are_identical_and_recover_the_fake_rates(tmp_path):
    big = dict(clips_per_region=20, speakers_per_region=10, seconds=0.5, words=100)
    first = pipeline(tmp_path, "a", **big)
    second = pipeline(tmp_path, "b", **big)
    for name in CSVS:
        assert (first / f"{name}.csv").read_bytes() == (second / f"{name}.csv").read_bytes()

    with open("config/fake.toml", "rb") as fh:
        rates = tomllib.load(fh)["error_rates"]
    summary = read_csv(first / "region_summary.csv")
    assert len(summary) == 6
    for row in summary:
        assert row["n_speakers"] == "10" and row["n_clips"] == "20" and row["low_n"] == "false"
        assert abs(float(row["wer"]) - rates[row["region"]]) < 0.03, row["region"]
        assert float(row["ci_lo"]) <= float(row["wer"]) <= float(row["ci_hi"])
