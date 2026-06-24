"""RestHostedModelProvider."""

from __future__ import annotations

import json

import pytest

from ianuacare.ai.providers.rest_hosted import RestHostedModelProvider, RestRequest
from ianuacare.core.exceptions.errors import InferenceError


def _build_stub(model_name: str, payload: dict) -> RestRequest:
    return RestRequest(
        headers={"X-Model": model_name, "Content-Type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
    )


def test_infer_uses_build_request_and_parse_response() -> None:
    captured: list[RestRequest] = []

    def post_fn(request: RestRequest, *, timeout_seconds: float) -> tuple[int, bytes, dict[str, str]]:
        _ = timeout_seconds
        captured.append(request)
        return 200, b'[[0.1, 0.2, 0.3]]', {"content-type": "application/json"}

    provider = RestHostedModelProvider(
        endpoint_url="https://example.test/v1",
        build_request=_build_stub,
        post_fn=post_fn,
    )
    out = provider.infer("emotion-v1", {"audio_path": "/tmp/a.wav"})
    assert out == [[0.1, 0.2, 0.3]]
    assert len(captured) == 1
    assert captured[0].url == "https://example.test/v1"
    assert captured[0].headers["X-Model"] == "emotion-v1"


def test_infer_adds_bearer_when_api_key_set() -> None:
    def post_fn(request: RestRequest, *, timeout_seconds: float) -> tuple[int, bytes, dict[str, str]]:
        _ = timeout_seconds
        assert request.headers["Authorization"] == "Bearer secret-token"
        return 200, b"{}", {}

    provider = RestHostedModelProvider(
        endpoint_url="https://example.test",
        api_key="secret-token",
        build_request=lambda _m, _p: RestRequest(headers={}),
        post_fn=post_fn,
    )
    provider.infer("m", {"audio_path": "/x.wav"})


def test_infer_does_not_override_existing_authorization() -> None:
    def post_fn(request: RestRequest, *, timeout_seconds: float) -> tuple[int, bytes, dict[str, str]]:
        _ = timeout_seconds
        assert request.headers["Authorization"] == "Custom scheme"
        return 200, b"{}", {}

    provider = RestHostedModelProvider(
        endpoint_url="https://example.test",
        api_key="ignored",
        build_request=lambda _m, _p: RestRequest(headers={"Authorization": "Custom scheme"}),
        post_fn=post_fn,
    )
    provider.infer("m", {"audio_path": "/x.wav"})


def test_infer_rejects_non_mapping_payload() -> None:
    provider = RestHostedModelProvider(
        endpoint_url="https://example.test",
        build_request=_build_stub,
        post_fn=lambda _r, timeout_seconds=0: (200, b"{}", {}),
    )
    with pytest.raises(ValueError, match="mapping"):
        provider.infer("m", "not-a-dict")


def test_default_parse_raises_on_error_status() -> None:
    provider = RestHostedModelProvider(
        endpoint_url="https://example.test",
        build_request=_build_stub,
        post_fn=lambda _r, timeout_seconds=0: (503, b"busy", {}),
    )
    with pytest.raises(InferenceError, match="503"):
        provider.infer("m", {"audio_path": "/x.wav"})


def test_build_request_can_override_url() -> None:
    def post_fn(request: RestRequest, *, timeout_seconds: float) -> tuple[int, bytes, dict[str, str]]:
        _ = timeout_seconds
        assert request.url == "https://override.test/infer"
        return 200, b"{}", {}

    provider = RestHostedModelProvider(
        endpoint_url="https://default.test",
        build_request=lambda _m, _p: RestRequest(url="https://override.test/infer"),
        post_fn=post_fn,
    )
    provider.infer("m", {"audio_path": "/x.wav"})
