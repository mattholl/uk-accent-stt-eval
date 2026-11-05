"""Transcriber protocol, error types and response checks shared by every backend."""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


class TranscribeError(Exception):
    pass


class HttpError(TranscribeError):
    def __init__(self, status: int, body: str = "", retry_after: float | None = None) -> None:
        super().__init__(f"HTTP {status}" + (f": {body}" if body else ""))
        self.status = status
        self.body = body
        self.retry_after = retry_after


class AuthOrQuotaError(HttpError):
    """401/402/403: the whole run stops."""


class ReadTimeout(TranscribeError):
    """The request was sent (it may already be billed), so it is not retried."""


class ConnectError(TranscribeError):
    """No response (the connection failed or was reset); retried. A reset after upload may be billed twice; accepted."""


class MalformedResponse(TranscribeError):
    pass


class Transcriber(Protocol):
    name: str

    def transcribe(self, audio_path: Path, params: Mapping[str, object]) -> dict: ...


def validate_response(raw: Mapping) -> None:
    """Raise MalformedResponse unless raw["text"] is a string."""
    if not isinstance(raw, Mapping) or not isinstance(raw.get("text"), str):
        raise MalformedResponse("response has no string 'text' field")


def wire_params(params: Mapping[str, object]) -> dict[str, str]:
    """Multipart form values: booleans as true/false, everything else str()."""
    return {k: ("true" if v else "false") if isinstance(v, bool) else str(v) for k, v in params.items()}
