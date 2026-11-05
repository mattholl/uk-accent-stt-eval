import json

import pytest

from ukstt.aggregate import n_digit_tokens_hyp, score_run, stats_run
from ukstt.audio import sha256_file
from ukstt.cli import main
from ukstt.constants import PILOT_REGIONS
from ukstt.csvio import fmt_float, read_csv, write_csv
from ukstt.stats import SpeakerCounts, bootstrap_ci

CLIP_COLUMNS = ["clip_id", "set", "speaker_id", "region", "task", "audio_path", "reference_path", "source", "notes"]


def make_run(tmp_path, clips, log=()):
    """clips: (clip_id, set, speaker, region, reference or None, hypothesis or None). Returns (run_dir, clips_csv, out_dir)."""
    run_dir = tmp_path / "runs" / "r1"
    (run_dir / "raw").mkdir(parents=True)
    rows = []
    for clip_id, set_name, speaker, region, ref, hyp in clips:
        ref_path = ""
        if ref is not None:
            ref_path = str(tmp_path / f"{clip_id}.txt")
            (tmp_path / f"{clip_id}.txt").write_text(ref + "\n")
        if hyp is not None:
            (run_dir / "raw" / f"{clip_id}.json").write_text(json.dumps({"text": hyp, "words": []}))
        task = "read" if set_name == "pilot" else "unknown"
        rows.append(dict(zip(CLIP_COLUMNS, [clip_id, set_name, speaker, region, task, "x.wav", ref_path, "t", ""])))
    clips_csv = tmp_path / "clips.csv"
    write_csv(clips_csv, rows, CLIP_COLUMNS)
    write_csv(run_dir / "transcribe_log.csv", [{"clip_id": c, "status": s} for c, s in log], ["clip_id", "status"])
    return run_dir, clips_csv, tmp_path / "results" / "r1"


CLIPS = [
    ("southern_a_1", "pilot", "sa", "southern", "the cat sat on the mat", "The cat sat."),         # D=3
    ("southern_a_2", "pilot", "sa", "southern", "red blue", "red green"),                          # S=1
    ("southern_b_1", "pilot", "sb", "southern", "a b c d", "a b c d e"),                           # I=1
    ("welsh_a_1", "pilot", "wa", "welsh", "the cat sat", "the dog sat"),                           # S=1
    ("welsh_a_2", "pilot", "wa", "welsh", "x y z", None),                                          # failed
    ("welsh_b_1", "pilot", "wb", "welsh", "x y z", None),                                          # missing
    ("demo_ref", "demo", "demo_ref", "unknown", "hello there", "hello"),                           # scored, utterance only
    ("demo_noref", "demo", "demo_noref", "unknown", None, "This is 2 fake and 3rd"),               # no_reference
]
LOG = [("welsh_a_2", "failed")]


@pytest.fixture
def scored(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, CLIPS, LOG)
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    return out


def table(out, name):
    return read_csv(out / f"{name}.csv")


def test_all_five_csvs_have_the_exact_columns(scored):
    cols = {
        "utterance_scores": "run_id,clip_id,set,speaker_id,region,task,status,n_ref,n_hyp,hits,subs,dels,ins,wer,n_digit_tokens_hyp,source",
        "speaker_scores": "region,task,speaker_id,n_clips,n_ref,subs,dels,ins,errors,wer",
        "region_summary": "task,region,n_speakers,n_clips,n_excluded,n_ref,subs,dels,ins,wer,ci_lo,ci_hi,low_n",
        "pairwise_vs_baseline": "task,region,n_spk_region,n_spk_base,wer_region,wer_base,diff,low_n",
        "error_pairs": "task,region,type,ref_word,hyp_word,count",
    }
    for name, header in cols.items():
        assert (scored / f"{name}.csv").read_text().splitlines()[0] == header


def test_utterance_statuses_and_counts(scored):
    rows = {r["clip_id"]: r for r in table(scored, "utterance_scores")}
    assert list(rows) == sorted(rows)
    assert {k: v["status"] for k, v in rows.items()} == {
        "southern_a_1": "ok", "southern_a_2": "ok", "southern_b_1": "ok", "welsh_a_1": "ok",
        "welsh_a_2": "failed", "welsh_b_1": "missing", "demo_ref": "ok", "demo_noref": "no_reference"}
    a = rows["southern_a_1"]
    assert (a["run_id"], a["n_ref"], a["n_hyp"], a["hits"], a["subs"], a["dels"], a["ins"], a["wer"]) == \
           ("r1", "6", "3", "3", "0", "3", "0", "0.500000")
    assert rows["southern_b_1"]["wer"] == "0.250000" and rows["southern_b_1"]["ins"] == "1"
    assert rows["demo_ref"]["wer"] == "0.500000"
    for clip_id in ("welsh_a_2", "welsh_b_1", "demo_noref"):
        assert rows[clip_id]["wer"] == "" and rows[clip_id]["hits"] == ""
    assert rows["demo_noref"]["n_digit_tokens_hyp"] == "2"
    assert rows["demo_noref"]["n_hyp"] != ""


def test_speaker_scores_pilot_ok_only_and_micro_averaged(scored):
    rows = {r["speaker_id"]: r for r in table(scored, "speaker_scores")}
    assert set(rows) == {"sa", "sb", "wa"}  # no demo clip, no failed/missing-only speaker
    sa = rows["sa"]
    assert (sa["n_clips"], sa["n_ref"], sa["subs"], sa["dels"], sa["ins"], sa["errors"], sa["wer"]) == \
           ("2", "8", "1", "3", "0", "4", "0.500000")  # (3+1)/(6+2), not the mean of 0.5 and 0.5 per clip


def test_region_summary_and_pairwise(scored):
    south, welsh = table(scored, "region_summary")
    assert (south["task"], south["region"], south["n_speakers"], south["n_clips"], south["n_excluded"]) == \
           ("read", "southern", "2", "3", "0")
    assert (south["n_ref"], south["subs"], south["dels"], south["ins"], south["wer"]) == ("12", "1", "3", "1", "0.416667")
    assert (south["ci_lo"], south["ci_hi"], south["low_n"]) == ("", "", "true")
    assert (welsh["region"], welsh["n_speakers"], welsh["n_clips"], welsh["n_excluded"], welsh["wer"]) == \
           ("welsh", "1", "1", "2", "0.333333")  # wb has no scored clip, so it is not a speaker
    (pair,) = table(scored, "pairwise_vs_baseline")
    assert (pair["region"], pair["n_spk_region"], pair["n_spk_base"], pair["wer_region"], pair["wer_base"],
            pair["diff"], pair["low_n"]) == ("welsh", "1", "2", "0.333333", "0.416667", "-0.083333", "true")


def test_error_pairs_ordering_and_ties(scored):
    southern = [(r["type"], r["ref_word"], r["hyp_word"], r["count"])
                for r in table(scored, "error_pairs") if r["region"] == "southern"]
    assert southern == [("ins", "", "e", "1"), ("sub", "blue", "green", "1"), ("del", "mat", "", "1"),
                        ("del", "on", "", "1"), ("del", "the", "", "1")]  # all tied: ref_word, then hyp_word
    assert {r["region"] for r in table(scored, "error_pairs")} == {"southern", "welsh"}  # no demo, no unknown


def test_error_pairs_highest_count_first(tmp_path):
    clips = [("c1", "pilot", "s1", "southern", "a b", "a x"), ("c2", "pilot", "s1", "southern", "b c", "x c"),
             ("c3", "pilot", "s2", "southern", "b d", "b")]
    run_dir, clips_csv, out = make_run(tmp_path, clips)
    score_run(run_dir, clips_csv, out)
    got = [(r["type"], r["ref_word"], r["hyp_word"], r["count"]) for r in table(out, "error_pairs")]
    assert got == [("sub", "b", "x", "2"), ("del", "d", "", "1")]


def test_baseline_missing_gives_empty_diff(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", "a c")])
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    (pair,) = table(out, "pairwise_vs_baseline")
    assert (pair["n_spk_base"], pair["wer_region"], pair["wer_base"], pair["diff"], pair["low_n"]) == \
           ("0", "0.500000", "", "", "true")


def test_region_with_only_failed_clips_has_empty_wer(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", None)])
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    (row,) = table(out, "region_summary")
    assert (row["n_speakers"], row["n_clips"], row["n_excluded"], row["wer"], row["low_n"]) == ("0", "0", "1", "", "true")


def test_ci_only_with_five_speakers(tmp_path):
    clips = [(f"c{i}", "pilot", f"s{i}", "welsh", "a b c d", "a b c x") for i in range(5)]
    clips += [(f"d{i}", "pilot", f"t{i}", "irish", "a b c d", "a b c x") for i in range(4)]
    run_dir, clips_csv, out = make_run(tmp_path, clips)
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    rows = {r["region"]: r for r in table(out, "region_summary")}
    assert (rows["welsh"]["ci_lo"], rows["welsh"]["ci_hi"], rows["welsh"]["low_n"]) == ("0.250000", "0.250000", "false")
    assert (rows["irish"]["ci_lo"], rows["irish"]["ci_hi"], rows["irish"]["low_n"]) == ("", "", "true")


def test_zero_word_reference_raises(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "um", "hello")])
    with pytest.raises(ValueError, match="w1"):
        score_run(run_dir, clips_csv, out)


def test_empty_hypothesis_is_all_deletions(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b c", "")])
    score_run(run_dir, clips_csv, out)
    (row,) = table(out, "utterance_scores")
    assert (row["status"], row["dels"], row["wer"], row["n_hyp"]) == ("ok", "3", "1.000000", "0")


def test_hypothesis_is_raw_text_only(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", "a b")])
    (run_dir / "raw" / "w1.json").write_text(json.dumps({"text": "a b", "words": [{"text": " ", "type": "spacing"}]}))
    score_run(run_dir, clips_csv, out)
    assert table(out, "utterance_scores")[0]["wer"] == "0.000000"


def test_n_digit_tokens_hyp():
    assert n_digit_tokens_hyp("") == 0
    assert n_digit_tokens_hyp("I paid £5 for 3rd class, 1990s and five") == 3
    assert n_digit_tokens_hyp("no digits here") == 0


def test_score_cli_refuses_changed_normalise_csv(tmp_path):
    run_dir, clips_csv, _ = make_run(tmp_path, CLIPS, LOG)
    cfg = tmp_path / "study.toml"
    cfg.write_text(f'[paths]\nruns_dir = "{tmp_path / "runs"}"\nresults_dir = "{tmp_path / "results"}"\n')
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps({"run_id": "r1", "normalise_csv_sha256": "0" * 64}))
    args = ["--config", str(cfg), "score", "--run-id", "r1", "--clips", str(clips_csv)]
    assert main(args) == 2
    assert not (tmp_path / "results" / "r1").exists()
    assert main(args + ["--accept-normalise-change"]) == 0
    assert json.loads(manifest_path.read_text())["normalise_csv_sha256"] == sha256_file("config/normalise.csv")
    assert main(args) == 0  # the hash now matches
    assert main(["--config", str(cfg), "stats", "--run-id", "r1"]) == 0
    assert len(table(tmp_path / "results" / "r1", "region_summary")) == 2


def test_score_and_stats_cli_errors_exit_2(tmp_path):
    cfg = tmp_path / "study.toml"
    cfg.write_text(f'[paths]\nruns_dir = "{tmp_path / "runs"}"\nresults_dir = "{tmp_path / "results"}"\n')
    assert main(["--config", str(cfg), "score", "--run-id", "nope"]) == 2  # no run_manifest.json
    assert main(["--config", str(cfg), "stats", "--run-id", "nope"]) == 2  # nothing scored yet


def test_speaker_wer_is_micro_averaged_not_mean_of_clips(tmp_path):
    clips = [("c1", "pilot", "s", "welsh", "a b c d e f", "a b c x y z"),  # 3/6
             ("c2", "pilot", "s", "welsh", "a b c d", "a b c x")]          # 1/4
    run_dir, clips_csv, out = make_run(tmp_path, clips)
    score_run(run_dir, clips_csv, out)
    (row,) = table(out, "speaker_scores")
    assert (row["errors"], row["n_ref"], row["wer"]) == ("4", "10", "0.400000")  # the mean of clips would be 0.375


def test_region_ci_uses_the_region_seed_key(tmp_path):
    shapes = [(10, 0), (7, 1), (13, 5), (9, 2), (20, 3), (11, 6), (8, 4)]  # (reference words, errors) per speaker
    clips = [(f"c{i}", "pilot", f"s{i}", "welsh", " ".join(f"w{j}" for j in range(n)),
              " ".join("x" if j < e else f"w{j}" for j in range(n))) for i, (n, e) in enumerate(shapes)]
    run_dir, clips_csv, out = make_run(tmp_path, clips)
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    sp = [SpeakerCounts(r["speaker_id"], int(r["errors"]), int(r["n_ref"])) for r in table(out, "speaker_scores")]
    lo, hi = bootstrap_ci(sp, "read|welsh")
    (row,) = table(out, "region_summary")
    assert (row["ci_lo"], row["ci_hi"]) == (fmt_float(lo), fmt_float(hi))
    assert bootstrap_ci(sp, "read|other") != (lo, hi)  # the key matters for these data


@pytest.mark.parametrize("content", ["null", '{"text": null}', '{"text": 5}', '{"text": ["a"]}', '{"words": []}',
                                     '["a"]', '"a"', "{not json"])
def test_bad_raw_file_names_the_clip_and_exits_2(tmp_path, capsys, content):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", "a b")])
    (run_dir / "raw" / "w1.json").write_text(content)
    with pytest.raises(ValueError, match="w1: bad raw file"):
        score_run(run_dir, clips_csv, out)
    cfg = write_cfg(tmp_path)
    (run_dir / "run_manifest.json").write_text(json.dumps({"normalise_csv_sha256": sha256_file("config/normalise.csv")}))
    assert main(["--config", str(cfg), "score", "--run-id", "r1", "--clips", str(clips_csv)]) == 2
    err = capsys.readouterr().err
    assert "w1: bad raw file" in err and "Traceback" not in err


def test_duplicate_clip_id_raises(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", "a b")])
    rows = read_csv(clips_csv)
    write_csv(clips_csv, rows + rows, CLIP_COLUMNS)
    with pytest.raises(ValueError, match="duplicate clip_id.*w1"):
        score_run(run_dir, clips_csv, out)


def write_cfg(tmp_path):
    cfg = tmp_path / "study.toml"
    cfg.write_text(f'[paths]\nruns_dir = "{tmp_path / "runs"}"\nresults_dir = "{tmp_path / "results"}"\n')
    return cfg


def test_stats_before_score_says_run_score_first(tmp_path, capsys):
    cfg = write_cfg(tmp_path)
    assert main(["--config", str(cfg), "stats", "--run-id", "r1"]) == 2
    assert "run score first (no utterance_scores.csv in" in capsys.readouterr().err


def test_failed_score_leaves_the_manifest_alone(tmp_path):
    run_dir, clips_csv, _ = make_run(tmp_path, [("w1", "pilot", "w", "welsh", "a b", "a b")])
    (run_dir / "raw" / "w1.json").write_text("null")
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps({"run_id": "r1", "normalise_csv_sha256": "0" * 64}))
    before = manifest_path.read_bytes()
    args = ["--config", str(write_cfg(tmp_path)), "score", "--run-id", "r1", "--clips", str(clips_csv)]
    assert main(args + ["--accept-normalise-change"]) == 2
    assert manifest_path.read_bytes() == before


def test_score_removes_stale_stats_files(tmp_path):
    run_dir, clips_csv, out = make_run(tmp_path, CLIPS, LOG)
    (run_dir / "run_manifest.json").write_text(json.dumps({"normalise_csv_sha256": sha256_file("config/normalise.csv")}))
    args = ["--config", str(write_cfg(tmp_path)), "--clips", str(clips_csv)]
    assert main(args[:2] + ["score", "--run-id", "r1", "--clips", str(clips_csv)]) == 0
    assert main(args[:2] + ["stats", "--run-id", "r1"]) == 0
    assert (out / "region_summary.csv").exists() and (out / "pairwise_vs_baseline.csv").exists()
    assert main(args[:2] + ["score", "--run-id", "r1", "--clips", str(clips_csv)]) == 0
    assert not (out / "region_summary.csv").exists() and not (out / "pairwise_vs_baseline.csv").exists()


@pytest.mark.parametrize("command", ["score", "stats"])
@pytest.mark.parametrize("run_id", ["../x", "a\n", "a/b", ""])
def test_bad_run_id_is_refused(tmp_path, capsys, command, run_id):
    assert main(["--config", str(write_cfg(tmp_path)), command, "--run-id", run_id]) == 2
    assert "run id may only contain" in capsys.readouterr().err


def test_regions_are_listed_in_pilot_order_in_every_table(tmp_path):
    names = list(PILOT_REGIONS)[::-1]  # reverse of the required order; alphabetical differs from it too
    clips = [(f"c{i}", "pilot", f"s{i}", r, "a b", "a x") for i, r in enumerate(names)]
    run_dir, clips_csv, out = make_run(tmp_path, clips)
    score_run(run_dir, clips_csv, out)
    stats_run(out)
    for name in ("speaker_scores", "error_pairs", "region_summary"):
        got = [r["region"] for r in table(out, name)]
        assert list(dict.fromkeys(got)) == list(PILOT_REGIONS), name
