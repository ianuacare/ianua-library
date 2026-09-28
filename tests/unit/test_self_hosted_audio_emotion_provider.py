"""Self-hosted emotion transport contract and bounded retry behavior."""

import base64
import json

import pytest

from ianuacare import InferenceError, SelfHostedAudioEmotionProvider

SCORES = {"arousal": 0.1, "dominance": 0.2, "valence": 0.3}


@pytest.mark.parametrize("source", ["bytes", "base64", "path"])
def test_request_and_response(source, tmp_path):
    def post(request, *, timeout_seconds):
        assert request.url == "https://emotion/infer"
        assert request.headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret",
        }
        assert timeout_seconds == 600
        assert json.loads(request.body) == {
            "model": "wavlm-emotion",
            "payload": {"audio_base64": base64.b64encode(b"wav").decode()},
        }
        return 200, json.dumps({"scores": SCORES}).encode(), {}

    path = tmp_path / "clip.wav"
    path.write_bytes(b"wav")
    payloads = {
        "bytes": {"audio_bytes": b"wav"},
        "base64": {"audio_base64": "d2F2"},
        "path": {"audio_path": str(path)},
    }
    provider = SelfHostedAudioEmotionProvider(
        "https://emotion/infer", api_key="secret", post_fn=post
    )
    assert provider.infer("wavlm-emotion", payloads[source]) == {"scores": SCORES}


@pytest.mark.parametrize("status", [400, 401, 413, 422, 500])
def test_server_errors_are_not_retried(status):
    calls = []

    def post(request, *, timeout_seconds):
        calls.append(request)
        return status, b'{"error":{"code":"invalid_audio","message":"Bad format"}}', {}

    provider = SelfHostedAudioEmotionProvider("https://emotion/infer", post_fn=post)
    with pytest.raises(InferenceError, match="invalid_audio: Bad format"):
        provider.infer("wavlm-emotion", {"audio_bytes": b"a"})
    assert len(calls) == 1


def test_retry_after_and_exhaustion():
    sleeps = []
    calls = []

    def post(request, *, timeout_seconds):
        calls.append(request)
        return 429, b'{"error":{"code":"busy","message":"Retry"}}', {"Retry-After": "2"}

    provider = SelfHostedAudioEmotionProvider(
        "https://emotion/infer", post_fn=post, sleep_fn=sleeps.append
    )
    with pytest.raises(InferenceError, match="busy: Retry"):
        provider.infer("wavlm-emotion", {"audio_bytes": b"a"})
    assert len(calls) == 3
    assert sleeps == [2, 2]


def test_retry_succeeds():
    responses = iter([(429, b"busy", {}), (200, json.dumps({"scores": SCORES}).encode(), {})])
    provider = SelfHostedAudioEmotionProvider(
        "https://emotion/infer",
        post_fn=lambda *a, **kw: next(responses),
        sleep_fn=lambda _: None,
    )
    assert provider.infer("wavlm-emotion", {"audio_bytes": b"a"})["scores"] == SCORES


@pytest.mark.parametrize("payload", [{}, {"audio_bytes": "wrong"}, {"audio_base64": "data:x"}])
def test_invalid_audio(payload):
    provider = SelfHostedAudioEmotionProvider("https://emotion/infer")
    with pytest.raises(ValueError):
        provider.infer("wavlm-emotion", payload)


def test_wrong_model_type():
    with pytest.raises(ValueError, match="only supports"):
        SelfHostedAudioEmotionProvider("https://emotion/infer").infer(
            "wavlm-emotion",
            {},
            model_type="llm",
        )


@pytest.mark.parametrize("body", [b"no-json", b"{}", b'{"scores":{"arousal":true}}'])
def test_invalid_response(body):
    provider = SelfHostedAudioEmotionProvider(
        "https://emotion/infer",
        post_fn=lambda *a, **kw: (200, body, {}),
    )
    with pytest.raises(InferenceError):
        provider.infer("wavlm-emotion", {"audio_bytes": b"a"})
