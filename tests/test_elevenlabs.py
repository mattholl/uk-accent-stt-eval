import json
import random
from dataclasses import replace
from pathlib import Path

import pytest
import requests
import responses

from ukstt.cli import main
from ukstt.config import load_config
from ukstt.csvio import read_csv
from ukstt.transcribe.base import wire_params
from ukstt.transcribe.fake import FakeTranscriber
from ukstt.transcribe.elevenlabs import ElevenLabsTranscriber, load_api_key
from ukstt.transcribe.runner import RunOptions, run_transcription

URL = ElevenLabsTranscriber.URL
KEY = 'dummy-key-for-tests-only-123'
CONFIG = Path(__file__).parent.parent / "config/study.toml"
GOOD = {"language_code": "eng", "language_probability": 1.0, "text": "Hello there.", "words": []}


@pytest.fixture(autouse=True)
def key_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", KEY)
    monkeypatch.chdir(tmp_path)  # so no real .env.local can be found


@pytest.fixture
def cfg(tmp_path):
    return replace(load_config(CONFIG), runs_dir=tmp_path / "runs")


def run(clipset, cfg, workers=1, cap=5.0, rows=None, run_id="r1"):
    path, all_rows = clipset
    opts = RunOptions(run_id, "elevenlabs", cap, workers, False, path)
    t = ElevenLabsTranscriber(KEY)
    return run_transcription(rows or all_rows, opts, cfg, t, lambda s: None)


def one(clipset):
    return clipset[0], clipset[1][:1]


def run_one(clipset, cfg):
    path, rows = one(clipset)
    return run_transcription(rows, RunOptions("r1", "elevenlabs", 5, 1, False, path), cfg,
                             ElevenLabsTranscriber(KEY), lambda s: None)


def test_wire_params_lowercase_booleans():
    assert wire_params({"a": True, "b": False, "c": 5, "d": "eng"}) == {"a": "true", "b": "false", "c": "5", "d": "eng"}


@responses.activate
def test_request_carries_header_and_every_param(clipset):
    responses.post(URL, json=GOOD)
    cfg_params = load_config(CONFIG).params
    audio = Path(clipset[1][0]["audio_path"])
    assert ElevenLabsTranscriber(KEY).transcribe(audio, cfg_params) == GOOD
    (call,) = responses.calls
    assert call.request.headers["xi-api-key"] == KEY
    body = call.request.body.decode("latin-1")
    for name, value in wire_params(cfg_params).items():
        assert f'name="{name}"\r\n\r\n{value}\r\n' in body
    assert 'name="tag_audio_events"\r\n\r\nfalse' in body
    assert "temperature" not in body
    assert f'name="file"; filename="{audio.name}"' in body


@responses.activate
def test_200_is_ok(clipset, cfg):
    responses.post(URL, json=GOOD)
    assert run_one(clipset, cfg) == 0
    row = read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]
    assert (row["status"], row["http_status"], row["backend"]) == ("ok", "200", "elevenlabs")
    assert json.loads(next((cfg.runs_dir / "r1/raw").glob("*.json")).read_text())["text"] == "Hello there."


@responses.activate
def test_read_timeout_is_not_retried(clipset, cfg):
    responses.post(URL, body=requests.ReadTimeout("slow"))
    assert run_one(clipset, cfg) == 4
    assert len(responses.calls) == 1
    assert read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]["error"].startswith("ReadTimeout")


@responses.activate
def test_connect_timeout_is_retried(clipset, cfg):
    responses.post(URL, body=requests.ConnectTimeout("no route"))
    responses.post(URL, json=GOOD)
    assert run_one(clipset, cfg) == 0
    assert len(responses.calls) == 2
    assert read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]["attempts"] == "2"


@responses.activate
def test_429_then_200(clipset, cfg):
    responses.post(URL, status=429, headers={"Retry-After": "2"}, json={"detail": "slow down"})
    responses.post(URL, json=GOOD)
    assert run_one(clipset, cfg) == 0
    assert len(responses.calls) == 2
    assert read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]["attempts"] == "2"


@responses.activate
def test_other_4xx_is_not_retried(clipset, cfg):
    responses.post(URL, status=422, json={"detail": "bad"})
    assert run_one(clipset, cfg) == 4
    assert len(responses.calls) == 1


@responses.activate
@pytest.mark.parametrize("status", [401, 402, 403])
def test_auth_or_quota_exits_5_and_stops(clipset, cfg, status):
    responses.post(URL, status=status, json={"detail": "no"})
    assert run(clipset, cfg) == 5
    assert len(responses.calls) == 1  # one worker: nothing further submitted
    assert not list((cfg.runs_dir / "r1/raw").glob("*.json"))


@responses.activate
@pytest.mark.parametrize("kwargs", [{"json": {"oops": 1}}, {"body": "<html>"}, {"json": [1, 2]}])
def test_malformed_200_fails_without_retry_or_raw_file(clipset, cfg, kwargs):
    responses.post(URL, status=200, **kwargs)
    assert run_one(clipset, cfg) == 4
    assert len(responses.calls) == 1
    assert not list((cfg.runs_dir / "r1/raw").glob("*.json"))
    assert "MalformedResponse" in read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]["error"]


@responses.activate
def test_gate_cap_is_enforced_without_http(clipset, cfg, capsys):
    assert run(clipset, cfg, cap=None) == 2
    assert run(clipset, cfg, cap=0.04) == 2  # 3 s of audio, 2.4 s allowed
    assert len(responses.calls) == 0 and not cfg.runs_dir.exists()
    assert "max-audio-minutes" in capsys.readouterr().err


@responses.activate
def test_gates_through_the_cli_make_no_http_calls(clipset, tmp_path, monkeypatch, capsys):
    path, _ = clipset
    base = ["--config", str(CONFIG), "transcribe", "--backend", "elevenlabs", "--clips", str(path), "--run-id", "x"]
    assert main(base) == 2  # no --max-audio-minutes
    assert main(base + ["--max-audio-minutes", "0.04"]) == 2  # too long in total
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert main(base + ["--max-audio-minutes", "5"]) == 2  # no key
    err = capsys.readouterr().err
    assert "ELEVENLABS_API_KEY" in err and "Traceback" not in err
    assert len(responses.calls) == 0


@responses.activate
def test_cli_real_backend_runs_with_cap(clipset, tmp_path):
    responses.post(URL, json=GOOD)
    path, rows = clipset
    conf = tmp_path / "s.toml"
    conf.write_text(f'[paths]\nruns_dir = "{tmp_path / "runs"}"\n')
    args = ["--config", str(conf), "transcribe", "--backend", "elevenlabs", "--clips", str(path), "--run-id", "x",
            "--max-audio-minutes", "1", "--workers", "20"]
    assert main(args) == 0
    assert len(responses.calls) == len(rows)


@responses.activate
def test_key_never_appears_in_logs_manifest_or_output(clipset, cfg, tmp_path, capsys, caplog):
    responses.post(URL, status=500, json={"detail": "boom"})
    responses.post(URL, json=GOOD)
    run(clipset, cfg)
    responses.replace(responses.POST, URL, status=401, json={"detail": "no"})
    assert run(clipset, cfg, run_id="r2") == 5
    out = capsys.readouterr()
    assert KEY not in out.out + out.err + caplog.text + repr(ElevenLabsTranscriber(KEY))
    for f in (tmp_path / "runs").rglob("*"):
        if f.is_file():
            assert KEY.encode() not in f.read_bytes(), f


def test_load_api_key_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    f = tmp_path / "env"
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        load_api_key(tmp_path / "missing")
    f.write_text("# ELEVENLABS_API_KEY=commented\nOTHER=x\nexport ELEVENLABS_API_KEY=\"abc123\"\n")
    assert load_api_key(f) == "abc123"
    f.write_text("ELEVENLABS_API_KEY=plain\n")
    assert load_api_key(f) == "plain"
    f.write_text("ELEVENLABS_API_KEY=\n")
    with pytest.raises(ValueError):
        load_api_key(f)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fromenv")
    assert load_api_key(f) == "fromenv"


@responses.activate
@pytest.mark.parametrize("header, expected", [
    ("5", 5), ("1e9", 60), ("inf", 2), ("nan", 2), ("-1", 2), ("soon", 2), ("Wed, 21 Oct 2026 07:28:00 GMT", 2)])
def test_retry_after_header_is_honoured_or_ignored(clipset, cfg, monkeypatch, header, expected):
    monkeypatch.setattr(random, "random", lambda: 0.0)  # first backoff is exactly 2 s
    responses.post(URL, status=429, headers={"Retry-After": header}, json={"detail": "slow"})
    responses.post(URL, json=GOOD)
    sleeps = []
    path, rows = one(clipset)
    opts = RunOptions("r1", "elevenlabs", 5, 1, False, path)
    assert run_transcription(rows, opts, cfg, ElevenLabsTranscriber(KEY), sleeps.append) == 0
    assert sleeps == [expected]


@responses.activate
def test_resume_of_a_fake_run_with_the_real_backend_exits_2_without_http(clipset, cfg, capsys):
    path, rows = clipset
    fake = FakeTranscriber.from_clips(path, CONFIG.parent / "fake.toml")
    assert run_transcription(rows, RunOptions("r1", "fake", None, 1, False, path), cfg, fake, lambda s: None) == 0
    next((cfg.runs_dir / "r1/raw").glob("*.json")).unlink()
    assert run(clipset, cfg) == 2
    assert "different backend" in capsys.readouterr().err
    assert len(responses.calls) == 0


@responses.activate
@pytest.mark.parametrize("cap", [float("nan"), float("inf"), 0, -1])
def test_bad_caps_make_no_http_calls(clipset, cfg, cap):
    assert run(clipset, cfg, cap=cap) == 2
    assert len(responses.calls) == 0 and not cfg.runs_dir.exists()


@responses.activate
def test_missing_audio_exits_2_with_zero_http_calls(clipset, cfg, capsys):
    Path(clipset[1][3]["audio_path"]).unlink()
    assert run(clipset, cfg) == 2
    assert "audio file not found" in capsys.readouterr().err
    assert len(responses.calls) == 0 and not cfg.runs_dir.exists()


@responses.activate
def test_redirect_is_not_followed(clipset, cfg):
    responses.post(URL, status=302, headers={"Location": "https://elsewhere.invalid/x"})
    assert run_one(clipset, cfg) == 4
    assert len(responses.calls) == 1
    row = read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]
    assert (row["status"], row["http_status"]) == ("failed", "302")


@responses.activate
def test_key_is_redacted_in_the_stored_error_body(clipset, cfg, tmp_path):
    responses.post(URL, status=401, json={"detail": f"invalid key {KEY} given"})
    assert run_one(clipset, cfg) == 5
    error = read_csv(cfg.runs_dir / "r1/transcribe_log.csv")[0]["error"]
    assert KEY not in error and "invalid key *** given" in error


@responses.activate
def test_lone_surrogate_in_the_response_is_stored(clipset, cfg):
    responses.post(URL, body='{"text": "a\\ud800b", "words": []}', content_type="application/json")
    assert run_one(clipset, cfg) == 0
    raw = next((cfg.runs_dir / "r1/raw").glob("*.json")).read_text(encoding="utf-8")
    assert json.loads(raw)["text"] == "a\ud800b"
