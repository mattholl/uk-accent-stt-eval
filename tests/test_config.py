import csv
import tomllib
from pathlib import Path

import pytest

from ukstt.config import load_config
from ukstt.constants import BASELINE, DEFAULT_PARAMS, PILOT_REGIONS

ROOT = Path(__file__).resolve().parent.parent


def write(tmp_path, body):
    path = tmp_path / "study.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_shipped_config_equals_the_defaults():
    cfg = load_config(ROOT / "config" / "study.toml")
    assert cfg.params == DEFAULT_PARAMS
    assert cfg.params["seed"] == 20261102 and cfg.params["tag_audio_events"] is False
    assert (cfg.max_retries, cfg.connect_timeout_s, cfg.read_timeout_s, cfg.default_workers) == (3, 10.0, 120.0, 4)
    assert (cfg.runs_dir, cfg.results_dir) == (Path("runs"), Path("results"))


def test_empty_file_gives_defaults_and_partial_file_overrides(tmp_path):
    assert load_config(write(tmp_path, "")) == load_config(ROOT / "config" / "study.toml")
    cfg = load_config(write(tmp_path, '[http]\nmax_retries = 1\n[paths]\nruns_dir = "r"\n'))
    assert cfg.max_retries == 1 and cfg.runs_dir == Path("r") and cfg.results_dir == Path("results")


@pytest.mark.parametrize("body", [
    "[nope]\nx = 1\n",
    "[params]\nnope = 1\n",
    "[http]\nnope = 1\n",
    '[paths]\nnope = "x"\n',
    '[params]\ndiarize = "false"\n',
    "[http]\nmax_retries = true\n",
])
def test_rejects_unknown_keys_and_wrong_types(tmp_path, body):
    path = write(tmp_path, body)
    with pytest.raises(ValueError) as exc:
        load_config(path)
    assert str(exc.value).startswith(f"{path}: ")


@pytest.mark.parametrize("body", [
    "[http]\nmax_retries = -1\n",
    "[http]\ndefault_workers = 0\n",
    "[http]\nconnect_timeout_s = 0\n",
    "[http]\nread_timeout_s = -5\n",
    "[http]\nconnect_timeout_s = inf\n",
    "[http]\nread_timeout_s = nan\n",
    "[params]\nseed = -1\n",
    "[params]\nseed = 2147483648\n",
    "[http]\ncredits_per_minute = 330\n",
    "[http\n",
])
def test_rejects_out_of_range_values(tmp_path, body):
    path = write(tmp_path, body)
    with pytest.raises(ValueError) as exc:
        load_config(path)
    assert str(exc.value).startswith(f"{path}: ")


def test_accepts_range_boundaries(tmp_path):
    cfg = load_config(write(tmp_path, "[http]\nmax_retries = 0\ndefault_workers = 1\n[params]\nseed = 2147483647\n"))
    assert (cfg.max_retries, cfg.default_workers, cfg.params["seed"]) == (0, 1, 2147483647)
    assert load_config(write(tmp_path, "[params]\nseed = 0\n")).params["seed"] == 0


def test_shipped_tables_agree_with_constants():
    with open(ROOT / "config" / "regions.csv", encoding="utf-8", newline="") as fh:
        regions = list(csv.DictReader(fh))
    assert [r["region_id"] for r in regions] == list(PILOT_REGIONS)
    assert [r["region_id"] for r in regions if r["is_baseline"] == "true"] == [BASELINE]
    assert all(r["is_baseline"] in ("true", "false") for r in regions)
    with open(ROOT / "config" / "fake.toml", "rb") as fh:
        assert tuple(tomllib.load(fh)["error_rates"]) == PILOT_REGIONS + ("unknown",)


def test_huge_integer_timeout_is_a_value_error_naming_the_file(tmp_path):
    path = write(tmp_path, "[http]\nread_timeout_s = 1" + "0" * 400 + "\n")
    with pytest.raises(ValueError) as exc:
        load_config(path)
    assert str(exc.value).startswith(f"{path}: ")
