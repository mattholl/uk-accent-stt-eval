import json
import random
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from ukstt.cli import main
from ukstt.config import load_config
from ukstt.csvio import read_csv
from ukstt.transcribe.base import AuthOrQuotaError, ConnectError, HttpError
from ukstt.transcribe.fake import FakeTranscriber
from ukstt.transcribe.runner import RunOptions, call_with_retry, run_transcription

NOSLEEP = lambda s: None  # noqa: E731


@pytest.fixture
def cfg(tmp_path):
    return replace(load_config(Path("config/study.toml")), runs_dir=tmp_path / "runs")


def opts(clips_csv, run_id="r1", workers=1, force=False, backend="fake", cap=None):
    return RunOptions(run_id, backend, cap, workers, force, clips_csv)


def fake_for(clips_csv, failures=None):
    t = FakeTranscriber.from_clips(clips_csv, Path("config/fake.toml"))
    t.failures = {k: list(v) for k, v in (failures or {}).items()}
    return t


def run(clipset, cfg, failures=None, transcriber=None, **kw):
    path, rows = clipset
    t = transcriber or fake_for(path, failures)
    return run_transcription(rows, opts(path, **kw), cfg, t, NOSLEEP)


def log_rows(cfg, run_id="r1"):
    return read_csv(cfg.runs_dir / run_id / "transcribe_log.csv")


class Counting:
    name = "fake"

    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def transcribe(self, audio_path, params):
        self.calls.append(Path(audio_path).stem)
        return self.inner.transcribe(audio_path, params)


def test_call_with_retry_sleeps_and_honours_retry_after():
    seen, sleeps = [], []

    def fn():
        seen.append(1)
        if len(seen) == 1:
            raise HttpError(429, retry_after=50)
        if len(seen) == 2:
            raise ConnectError("x")
        return "done"

    assert call_with_retry(fn, max_retries=3, sleep=sleeps.append) == "done"
    assert sleeps[0] == 50 and 4 <= sleeps[1] < 5


@pytest.mark.parametrize("exc", [HttpError(400), HttpError(404), AuthOrQuotaError(401)])
def test_call_with_retry_does_not_retry_other_4xx(exc):
    calls = []

    def fn():
        calls.append(1)
        raise exc

    with pytest.raises(HttpError):
        call_with_retry(fn, max_retries=3, sleep=NOSLEEP)
    assert len(calls) == 1


def test_clean_run_writes_everything(clipset, cfg, capsys):
    assert run(clipset, cfg) == 0
    d = cfg.runs_dir / "r1"
    rows = log_rows(cfg)
    assert [r["status"] for r in rows] == ["ok"] * 6
    assert [r["clip_id"] for r in rows] == sorted(r["clip_id"] for r in clipset[1])
    assert len(list((d / "raw").glob("*.json"))) == 6 and not list(d.rglob("*.tmp"))
    assert json.loads((d / "raw" / "welsh_01_01.json").read_text())["text"]
    assert (d / "clips.csv").read_bytes() == clipset[0].read_bytes()
    m = json.loads((d / "run_manifest.json").read_text())
    assert m["backend"] == "fake" and m["params"]["tag_audio_events"] == "false" and len(m["clips_file_sha256"]) == 64
    assert "6 ok, 0 skipped, 0 failed" in capsys.readouterr().out


def test_429_429_ok_takes_three_attempts(clipset, cfg):
    assert run(clipset, cfg, failures={"welsh_01_01": ["429", "429"]}) == 0
    row = next(r for r in log_rows(cfg) if r["clip_id"] == "welsh_01_01")
    assert (row["status"], row["attempts"]) == ("ok", "3")


def test_500_four_times_fails_with_exit_4(clipset, cfg):
    assert run(clipset, cfg, failures={"welsh_01_01": ["500"] * 4}) == 4
    row = next(r for r in log_rows(cfg) if r["clip_id"] == "welsh_01_01")
    assert (row["status"], row["attempts"], row["http_status"]) == ("failed", "4", "500")
    assert "HttpError" in row["error"]
    assert not (cfg.runs_dir / "r1/raw/welsh_01_01.json").exists()


def test_timeout_is_not_retried(clipset, cfg):
    assert run(clipset, cfg, failures={"welsh_01_01": ["timeout", "timeout"]}) == 4
    row = next(r for r in log_rows(cfg) if r["clip_id"] == "welsh_01_01")
    assert (row["status"], row["attempts"]) == ("failed", "1")


def test_malformed_is_rejected_and_not_written(clipset, cfg):
    assert run(clipset, cfg, failures={"welsh_01_01": ["malformed"]}) == 4
    row = next(r for r in log_rows(cfg) if r["clip_id"] == "welsh_01_01")
    assert row["status"] == "failed" and "MalformedResponse" in row["error"] and row["attempts"] == "1"
    assert not (cfg.runs_dir / "r1/raw/welsh_01_01.json").exists()


def test_empty_response_is_valid(clipset, cfg):
    assert run(clipset, cfg, failures={"welsh_01_01": ["empty"]}) == 0
    assert json.loads((cfg.runs_dir / "r1/raw/welsh_01_01.json").read_text())["text"] == ""


def test_resume_after_a_crash_redoes_only_the_missing_clip(clipset, cfg):
    assert run(clipset, cfg) == 0
    (cfg.runs_dir / "r1/raw/irish_01_01.json").unlink()
    (cfg.runs_dir / "r1/raw/midlands_01_01.json.tmp").write_text("{")  # half-written leftover
    spy = Counting(fake_for(clipset[0]))
    assert run(clipset, cfg, transcriber=spy) == 0
    assert spy.calls == ["irish_01_01"]
    statuses = [r["status"] for r in log_rows(cfg)]
    assert statuses.count("ok") == 7 and statuses.count("skipped") == 5


def test_existing_raw_is_skipped_and_force_sends_again(clipset, cfg):
    assert run(clipset, cfg) == 0
    spy = Counting(fake_for(clipset[0]))
    assert run(clipset, cfg, transcriber=spy) == 0 and spy.calls == []
    assert [r["status"] for r in log_rows(cfg)][6:] == ["skipped"] * 6
    assert run(clipset, cfg, transcriber=spy, force=True) == 0 and len(spy.calls) == 6


def raw_texts(cfg, run_id):
    return {p.name: p.read_text() for p in (cfg.runs_dir / run_id / "raw").glob("*.json")}


def test_eight_workers_equal_one_worker(clipset, cfg):
    assert run(clipset, cfg, run_id="w1", workers=1) == 0
    assert run(clipset, cfg, run_id="w8", workers=8) == 0
    assert raw_texts(cfg, "w1") == raw_texts(cfg, "w8")
    key = lambda r: (r["clip_id"], r["status"], r["attempts"])  # noqa: E731
    assert sorted(map(key, log_rows(cfg, "w1"))) == sorted(map(key, log_rows(cfg, "w8")))


def test_workers_above_eight_are_clamped(clipset, cfg, monkeypatch):
    import ukstt.transcribe.runner as runner

    sizes = []
    real = runner.ThreadPoolExecutor
    monkeypatch.setattr(runner, "ThreadPoolExecutor", lambda max_workers: sizes.append(max_workers) or real(max_workers))
    assert run(clipset, cfg, workers=50) == 0
    assert sizes == [8]


def test_manifest_mismatch_exits_2(clipset, cfg, capsys):
    assert run(clipset, cfg) == 0
    path, rows = clipset
    other = replace(cfg, params={**cfg.params, "seed": 1})
    assert run_transcription(rows, opts(path), other, fake_for(path), NOSLEEP) == 2
    assert "different params" in capsys.readouterr().err
    path.write_text(path.read_text() + "\n")  # same rows, different file bytes
    assert run(clipset, cfg) == 2
    assert run(clipset, cfg, force=True) == 2


def test_bad_run_id_and_duplicate_clips_exit_2(clipset, cfg):
    assert run(clipset, cfg, run_id="../x") == 2
    path, rows = clipset
    assert run_transcription(rows + rows[:1], opts(path), cfg, fake_for(path), NOSLEEP) == 2
    assert not cfg.runs_dir.exists()


def test_auth_error_exits_5_and_submits_nothing_further(clipset, cfg):
    class Denied:
        name = "fake"
        calls = 0

        def transcribe(self, audio_path, params):
            Denied.calls += 1
            raise AuthOrQuotaError(401, "denied")

    assert run(clipset, cfg, transcriber=Denied()) == 5
    assert Denied.calls == 1
    rows = log_rows(cfg)
    assert [(r["status"], r["http_status"]) for r in rows] == [("failed", "401")]
    assert not list((cfg.runs_dir / "r1/raw").glob("*.json"))


def test_cap_applies_to_clips_still_to_send(clipset, cfg):
    assert run(clipset, cfg, cap=0.04) == 2  # 6 x 0.5 s = 3 s > 2.4 s
    assert not cfg.runs_dir.exists()
    assert run(clipset, cfg, cap=0.06) == 0
    assert run(clipset, cfg, cap=0.001) == 0  # everything is skipped, so nothing is sent
    assert run(clipset, cfg, cap=0.001, force=True) == 2


def test_cli_dummy_pilot_run_then_resume(tmp_path, capsys):
    out = tmp_path / "dummy"
    m = out / "manifests"
    assert main(["make-dummy-data", "--out", str(out), "--seconds", "1"]) == 0
    assert main(["build-manifest", "--in", str(m / "clips_in.csv"), "--out", str(m / "clips.csv"),
                 "--report", str(m / "report.csv")]) == 0
    assert main(["select", "--clips", str(m / "clips.csv"), "--stage", "pilot"]) == 0
    runs = tmp_path / "runs"
    conf = tmp_path / "study.toml"
    conf.write_text(f'[paths]\nruns_dir = "{runs}"\n')
    args = ["--config", str(conf), "transcribe", "--clips", str(m / "pilot.csv"), "--run-id", "dummy-pilot-001"]
    assert main(args) == 0
    assert [r["status"] for r in read_csv(runs / "dummy-pilot-001/transcribe_log.csv")] == ["ok"] * 24
    assert main(args) == 0
    statuses = [r["status"] for r in read_csv(runs / "dummy-pilot-001/transcribe_log.csv")]
    assert statuses.count("ok") == 24 and statuses.count("skipped") == 24
    assert "0 ok, 24 skipped" in capsys.readouterr().out


def test_cli_user_errors_exit_2(tmp_path, capsys):
    assert main(["transcribe", "--clips", str(tmp_path / "none.csv"), "--run-id", "x"]) == 2
    assert capsys.readouterr().err.startswith("error: ")


def test_ctrl_c_stops_sending_queued_clips(clipset, cfg):
    release, calls = threading.Event(), []

    class Interrupted:
        name = "fake"

        def transcribe(self, audio_path, params):
            calls.append(Path(audio_path).stem)
            if len(calls) == 1:
                raise KeyboardInterrupt
            release.wait(0.3)  # the other worker is busy while the pool is shut down
            return {"text": "x", "words": []}

    with pytest.raises(KeyboardInterrupt):
        run(clipset, cfg, transcriber=Interrupted(), workers=2)
    assert len(calls) < 6  # queued clips are cancelled (how many workers had already started one is timing-dependent)


@pytest.mark.parametrize("value, expected", [
    (5, 5), (60, 60), (1e9, 60), (float("inf"), 2), (float("nan"), 2), (-3, 2), ("garbage", 2), (None, 2)])
def test_retry_after_is_finite_non_negative_and_capped(monkeypatch, value, expected):
    monkeypatch.setattr(random, "random", lambda: 0.0)  # first backoff is exactly 2 s
    seen, sleeps = [], []

    def fn():
        seen.append(1)
        if len(seen) == 1:
            raise HttpError(429, retry_after=value)
        return "done"

    assert call_with_retry(fn, max_retries=1, sleep=sleeps.append) == "done"
    assert sleeps == [expected]


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), 0, -1])
def test_bad_audio_caps_exit_2(clipset, cfg, cap, capsys):
    assert run(clipset, cfg, cap=cap) == 2
    assert "finite" in capsys.readouterr().err and not cfg.runs_dir.exists()


def test_transcriber_must_match_backend(clipset, cfg, capsys):
    assert run(clipset, cfg, backend="elevenlabs", cap=5) == 2  # a fake transcriber behind the real label
    assert "--backend" in capsys.readouterr().err and not cfg.runs_dir.exists()


def test_run_id_with_trailing_newline_is_refused(clipset, cfg):
    assert run(clipset, cfg, run_id="r1\n") == 2
    assert not cfg.runs_dir.exists()


def test_missing_audio_exits_2_before_anything_is_sent(clipset, cfg, capsys):
    Path(clipset[1][2]["audio_path"]).unlink()
    spy = Counting(fake_for(clipset[0]))
    assert run(clipset, cfg, transcriber=spy) == 2
    assert "audio file not found" in capsys.readouterr().err
    assert spy.calls == [] and not cfg.runs_dir.exists()


def test_os_error_is_a_failed_clip(clipset, cfg):
    class Unreadable(Counting):
        def transcribe(self, audio_path, params):
            if Path(audio_path).stem == "welsh_01_01":
                raise PermissionError("denied")
            return super().transcribe(audio_path, params)

    assert run(clipset, cfg, transcriber=Unreadable(fake_for(clipset[0]))) == 4
    rows = {r["clip_id"]: r for r in log_rows(cfg)}
    assert rows["welsh_01_01"]["status"] == "failed" and "PermissionError" in rows["welsh_01_01"]["error"]
    assert [r["status"] for r in rows.values()].count("ok") == 5


def test_log_header_is_written_into_an_empty_log(clipset, cfg):
    (cfg.runs_dir / "r1").mkdir(parents=True)
    (cfg.runs_dir / "r1/transcribe_log.csv").write_text("")
    assert run(clipset, cfg) == 0
    assert len(log_rows(cfg)) == 6  # read_csv would take a row for the header if it were missing


def test_to_send_line_fake_backend(clipset, cfg, capsys):
    assert run(clipset, cfg) == 0
    out = capsys.readouterr().out
    assert "to send (fake): 6 clips, 0.05 min\n" in out and "credits" not in out
    assert run(clipset, cfg) == 0  # resume: nothing left to send
    assert "to send (fake): 0 clips, 0.00 min\n" in capsys.readouterr().out


def test_to_send_line_elevenlabs_is_resume_aware(clipset, cfg, capsys):
    path, rows = clipset
    rows = [{**r, "duration_s": "60"} for r in rows]  # 6 min in all
    t = fake_for(path)
    t.name = "elevenlabs"  # no HTTP here: the transcriber is still the fake one
    assert run_transcription(rows, opts(path, backend="elevenlabs", cap=10), cfg, t, NOSLEEP) == 0
    first = capsys.readouterr().out
    assert ("to send: 6 clips, 6.00 min (about 1980 credits at 330 credits/min, "
            "unverified; check the dashboard)\n") in first
    (cfg.runs_dir / "r1/raw/irish_01_01.json").unlink()
    assert run_transcription(rows, opts(path, backend="elevenlabs", cap=10), cfg, t, NOSLEEP) == 0
    assert "to send: 1 clips, 1.00 min (about 330 credits" in capsys.readouterr().out


def test_to_send_line_is_not_printed_when_the_gate_refuses(clipset, cfg, capsys):
    assert run(clipset, cfg, cap=0.001) == 2
    assert "to send" not in capsys.readouterr().out
