"""Study configuration: config/study.toml -> frozen dataclass."""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ukstt.constants import DEFAULT_HTTP, DEFAULT_PARAMS, DEFAULT_PATHS

DEFAULT_CONFIG = Path("config/study.toml")


@dataclass(frozen=True)
class StudyConfig:
    params: dict[str, object]  # native types; sent via wire_params()

    max_retries: int
    connect_timeout_s: float
    read_timeout_s: float
    default_workers: int
    runs_dir: Path
    results_dir: Path


def _merge(section: str, given: object, defaults: dict[str, object]) -> dict[str, object]:
    """Defaults overlaid with the file's table. Unknown keys and wrong value types are rejected."""
    if not isinstance(given, dict):
        raise ValueError(f"[{section}] must be a table")
    unknown = sorted(set(given) - set(defaults))
    if unknown:
        raise ValueError(f"unknown key(s) in [{section}]: {', '.join(unknown)}")
    for key, value in given.items():
        want = type(defaults[key])
        if type(value) is not want and not (want is float and type(value) is int):
            raise ValueError(f"[{section}] {key} must be {want.__name__}, got {type(value).__name__}")
    return {**defaults, **given}


def load_config(path: Path = DEFAULT_CONFIG) -> StudyConfig:
    """Read and validate the file; every ValueError message starts with the path."""
    try:
        return _load(path)
    except (ValueError, OverflowError) as exc:  # TOMLDecodeError is a ValueError; float() of a huge int overflows
        raise ValueError(f"{path}: {exc}") from exc


def _load(path: Path) -> StudyConfig:
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    unknown = sorted(set(raw) - {"params", "http", "paths"})
    if unknown:
        raise ValueError(f"unknown section(s): {', '.join(unknown)}")
    params = _merge("params", raw.get("params", {}), DEFAULT_PARAMS)
    http = _merge("http", raw.get("http", {}), DEFAULT_HTTP)
    paths = _merge("paths", raw.get("paths", {}), DEFAULT_PATHS)
    connect, read = float(http["connect_timeout_s"]), float(http["read_timeout_s"])
    if http["max_retries"] < 0:
        raise ValueError("[http] max_retries must be >= 0")
    if http["default_workers"] < 1:
        raise ValueError("[http] default_workers must be >= 1")
    for name, value in (("connect_timeout_s", connect), ("read_timeout_s", read)):
        if not 0 < value < math.inf:
            raise ValueError(f"[http] {name} must be finite and > 0")
    if not 0 <= params["seed"] <= 2147483647:
        raise ValueError("[params] seed must be in 0..2147483647")
    return StudyConfig(
        params=params,
        max_retries=http["max_retries"],
        connect_timeout_s=connect,
        read_timeout_s=read,
        default_workers=http["default_workers"],
        runs_dir=Path(paths["runs_dir"]),
        results_dir=Path(paths["results_dir"]),
    )
