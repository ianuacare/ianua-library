"""Adapter for the self-hosted wavlm-emotion JSON contract."""

from __future__ import annotations

import base64
import json
import math
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from ianuacare.ai.providers.base import AIProvider
from ianuacare.ai.providers.rest_hosted import PostFn, RestHostedModelProvider, RestRequest
from ianuacare.core.exceptions.errors import InferenceError


class _RateLimited(InferenceError):
    def __init__(self, message: str, headers: Mapping[str, str]) -> None:
        super().__init__(message)
        value = next((v for k, v in headers.items() if k.lower() == "retry-after"), "1")
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = 1.0
        self.delay = max(0.0, delay) if math.isfinite(delay) else 1.0


def _build_request(model_name: str, payload: Any) -> RestRequest:
    audio = payload.get("audio_bytes")
    if audio is None and payload.get("audio_path") is not None:
        try:
            audio = Path(payload["audio_path"]).read_bytes()
        except (OSError, TypeError) as exc:
            raise InferenceError("Cannot read audio_path") from exc
    encoded = payload.get("audio_base64")
    if audio is not None:
        if not isinstance(audio, bytes) or not audio:
            raise ValueError("audio_bytes must be non-empty bytes")
        encoded = base64.b64encode(audio).decode("ascii")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("audio_bytes or audio_base64 is required")
    try:
        if not base64.b64decode(encoded, validate=True):
            raise ValueError("empty audio")
    except ValueError as exc:
        raise ValueError("audio_base64 must contain plain valid base64") from exc
    return RestRequest(
        headers={"Content-Type": "application/json"},
        body=json.dumps({"model": model_name, "payload": {"audio_base64": encoded}}).encode(),
    )


def _parse_response(status_code: int, body: bytes, *, headers: Mapping[str, str]) -> Any:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        if 200 <= status_code < 300:
            raise InferenceError("audio emotion endpoint returned non-JSON body") from exc
        data = {}
    if not 200 <= status_code < 300:
        error = data.get("error", {}) if isinstance(data, dict) else {}
        detail = (
            f"{error.get('code', '')}: {error.get('message', '')}"
            if isinstance(error, dict)
            else str(error)
        )
        message = f"audio emotion endpoint returned status {status_code}: {detail}"
        if status_code == 429:
            raise _RateLimited(message, headers)
        raise InferenceError(message)
    scores = data.get("scores") if isinstance(data, dict) else None
    if not isinstance(scores, dict) or any(
        isinstance(scores.get(k), bool)
        or not isinstance(scores.get(k), (int, float))
        or not math.isfinite(scores[k])
        for k in ("arousal", "dominance", "valence")
    ):
        raise InferenceError("audio emotion response requires finite ADV scores")
    return data


class SelfHostedAudioEmotionProvider(AIProvider):
    """POST audio to /infer; retry only HTTP 429, at most ``max_retries`` times."""

    def __init__(
        self,
        endpoint_url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 600.0,
        max_retries: int = 2,
        post_fn: PostFn | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        self._max_retries = max_retries
        self._sleep = sleep_fn or time.sleep
        self._rest = RestHostedModelProvider(
            endpoint_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            build_request=_build_request,
            parse_response=_parse_response,
            post_fn=post_fn,
        )

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if model_type not in (None, "audio_emotion"):
            raise ValueError("SelfHostedAudioEmotionProvider only supports audio_emotion")
        for attempt in range(self._max_retries + 1):
            try:
                return self._rest.infer(model_name, payload, params=params)
            except _RateLimited as exc:
                if attempt == self._max_retries:
                    raise
                self._sleep(exc.delay)
