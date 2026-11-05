"""ElevenLabs Scribe speech-to-text over one multipart POST (no retry here)."""

import os
from collections.abc import Mapping
from pathlib import Path

import requests

from ukstt.transcribe.base import (AuthOrQuotaError, ConnectError, HttpError, MalformedResponse,
                                   ReadTimeout, TranscribeError, wire_params)

KEY_VAR = "ELEVENLABS_API_KEY"
ENV_FILE = Path(".env.local")


def load_api_key(env_file: Path = ENV_FILE) -> str:
    """The key from the environment, else from env_file. Other .env* files are never read."""
    key = os.environ.get(KEY_VAR, "").strip()
    if key:
        return key
    if Path(env_file).is_file():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip().removeprefix("export ").strip()
            name, _, value = line.partition("=")
            if name.strip() == KEY_VAR:
                value = value.strip().strip("\"'")
                if value:
                    return value
    raise ValueError(f"no API key: set {KEY_VAR} in the environment or in {env_file}")


class ElevenLabsTranscriber:
    name = "elevenlabs"
    URL = "https://api.elevenlabs.io/v1/speech-to-text"

    def __init__(self, api_key: str, connect_timeout_s: float = 10, read_timeout_s: float = 120,
                 session: requests.Session | None = None) -> None:
        self._key = api_key
        self.timeout = (connect_timeout_s, read_timeout_s)
        self.session = session or requests.Session()

    def transcribe(self, audio_path: Path, params: Mapping[str, object]) -> dict:
        audio_path = Path(audio_path)
        try:
            with open(audio_path, "rb") as fh:
                resp = self.session.post(self.URL, headers={"xi-api-key": self._key}, data=wire_params(params),
                                         files={"file": (audio_path.name, fh, "audio/wav")}, timeout=self.timeout,
                                         allow_redirects=False)
        except requests.ReadTimeout as exc:
            raise ReadTimeout(f"read timeout after {self.timeout[1]} s") from exc
        except requests.ConnectionError as exc:  # includes ConnectTimeout
            raise ConnectError(type(exc).__name__) from exc
        except requests.RequestException as exc:
            raise TranscribeError(type(exc).__name__) from exc
        if resp.status_code != 200:
            retry_after = None
            try:
                retry_after = float(resp.headers.get("Retry-After", ""))
            except ValueError:
                pass
            cls = AuthOrQuotaError if resp.status_code in (401, 402, 403) else HttpError
            body = resp.text.replace(self._key, "***")[:200].replace("\n", " ")
            raise cls(resp.status_code, body, retry_after)
        try:
            data = resp.json()
        except ValueError as exc:
            raise MalformedResponse("response body is not JSON") from exc
        if not isinstance(data, dict):
            raise MalformedResponse("response JSON is not an object")
        return data
