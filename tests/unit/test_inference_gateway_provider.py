"""Gateway HTTP contract, model compatibility and durable async job handling."""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error
from typing import Any

import pytest

from ianuacare import (
    GatewayHTTPError,
    GatewayJobPending,
    InferenceGatewayProvider,
    LLMModel,
    ModelOutNormalizer,
    TextEmbedder,
)
from ianuacare.ai.providers.rest_hosted import RestRequest
from ianuacare.core.exceptions import InferenceError


class Transport:
    def __init__(self, *responses: tuple[int, Any]) -> None:
        self.responses = list(responses)
        self.requests: list[RestRequest] = []

    def __call__(self, request: RestRequest, *, timeout_seconds: float):
        assert timeout_seconds == 600
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return status, json.dumps(body).encode(), {"Retry-After": "5"}


def completed(**kwargs):
    return {"model": "query", "provider": "ec2", "status": "completed", **kwargs}


def job(status="queued", **kwargs):
    return {
        "model": "ocr",
        "provider": "sagemaker",
        "status": status,
        "job_id": "abc123",
        "status_url": "https://untrusted.example/steal-key",
        **kwargs,
    }


def test_wire_envelope_auth_and_completed_ocr():
    raw = {"model": "ocr", "status": "completed", "text": "Documento", "raw": {"stub": True}}
    post = Transport((200, raw))
    provider = InferenceGatewayProvider(
        "https://gateway.test/prefix/", api_key="secret", post_fn=post
    )
    result = provider.infer("ocr", {"image_b64": "image"}, params={"max_new_tokens": 100})
    assert result == raw
    request = post.requests[0]
    assert request.url == "https://gateway.test/prefix/infer"
    assert request.method == "POST"
    assert request.headers["Authorization"] == "Bearer secret"
    assert json.loads(request.body) == {
        "model": "ocr",
        "payload": {"image_b64": "image"},
        "params": {"max_new_tokens": 100},
    }


def test_embedding_batches_preserve_order_for_existing_text_embedder():
    post = Transport(
        (200, completed(embeddings=[[1, 2], [3, 4]])),
        (200, completed(embeddings=[[5, 6], [7, 8]])),
    )
    provider = InferenceGatewayProvider("https://gateway.test", batch_size=2, post_fn=post)
    embedder = TextEmbedder(provider=provider, model_name="query")
    result = embedder.run(
        {
            "id_artefatto_trascrizione": "test",
            "text": "a b",
            "chunks": ["a", "b"],
            "sentences": ["a b"],
            "words": ["a"],
        }
    )
    assert result["text_vect"] == [2.0, 3.0]
    assert result["chunks_vect"] == [[1.0, 2.0], [3.0, 4.0]]
    assert result["sentence_vect"] == [[5.0, 6.0]]
    assert result["words_vect"] == [[7.0, 8.0]]
    assert [json.loads(r.body)["payload"]["texts"] for r in post.requests] == [
        ["a", "b"],
        ["a b", "a"],
    ]


def test_empty_embeddings_do_not_make_http_requests():
    post = Transport()
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    assert provider.infer("query", [], model_type="embedding") == []
    assert post.requests == []


@pytest.mark.parametrize(
    "vectors", [None, [[1], [1, 2]], [[True]], [[float("nan")]], [["x"]], [[]], [[10**400]]]
)
def test_invalid_vectors_rejected(vectors):
    provider = InferenceGatewayProvider(
        "https://gateway.test",
        post_fn=Transport(
            (200, completed(embeddings=vectors)),
        ),
    )
    with pytest.raises(InferenceError):
        provider.infer("query", ["a"], model_type="embedding")


def test_vector_count_must_match_batch():
    provider = InferenceGatewayProvider(
        "https://gateway.test",
        post_fn=Transport(
            (200, completed(embeddings=[[1, 2]])),
        ),
    )
    with pytest.raises(InferenceError, match="count"):
        provider.infer("query", ["a", "b"], model_type="embedding")


def test_llm_model_uses_existing_prompt_contract_and_preserves_raw_blocks():
    message = {
        "role": "assistant",
        "content": [
            {"reasoningContent": {"reasoningText": {"signature": "signed", "text": "internal"}}},
            {"text": "Risposta"},
        ],
    }
    raw = {
        "model": "llm",
        "status": "completed",
        "text": "Risposta",
        "message": message,
        "usage": {"inputTokens": 10},
    }
    post = Transport((200, raw), (200, raw))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    fields = {"thinking": {"type": "between_tools"}, "output_config": {"effort": "medium"}}
    llm = LLMModel(
        provider,
        "llm",
        ModelOutNormalizer(),
        temperature=None,
        top_p=None,
        max_tokens=50,
        additional_model_fields=fields,
    )
    assert llm.run({"prompt": "Contesto e domanda", "text": "Domanda"})["text"] == "Risposta"
    body = json.loads(post.requests[0].body)
    assert body["payload"] == {"messages": [{"role": "user", "content": "Contesto e domanda"}]}
    assert body["params"] == {"max_tokens": 50, "additional_model_fields": fields}
    result = provider.infer("llm", [{"role": "user", "content": "Domanda"}])
    assert result["message"] == message and result["usage"] == {"inputTokens": 10}
    assert provider.supports_tools is False


@pytest.mark.parametrize("state", ["queued", "pending", "submission_unknown"])
def test_infer_never_mistakes_job_for_completed_result(state):
    post = Transport((202, job(state)))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(GatewayJobPending) as caught:
        provider.infer("ocr", {"image_b64": "x"})
    assert caught.value.job_id == "abc123" and caught.value.status == state
    assert caught.value.model_name == "ocr"
    assert len(post.requests) == 1


def test_submit_and_consult_job_after_provider_recreation():
    post = Transport(
        (202, job()),
        (200, job("pending")),
        (200, job("completed", result={"text": "Documento", "raw": {"stub": True}})),
    )
    first = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    reference = first.submit("ocr", {"image_b64": "x"})
    restored = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(GatewayJobPending):
        restored.get_result(reference["model"], reference["job_id"])
    assert restored.get_result("ocr", "abc123")["text"] == "Documento"
    assert post.requests[1].url == "https://gateway.test/jobs/ocr/abc123"
    assert post.requests[1].method == "GET" and post.requests[1].body is None
    assert len(post.requests) == 3


def test_submit_does_not_implicitly_split_or_wait_for_async_embeddings():
    post = Transport((202, {**job(), "model": "document-embeddings"}))
    provider = InferenceGatewayProvider("https://gateway.test", batch_size=1, post_fn=post)
    provider.submit("document-embeddings", ["a", "b"], model_type="embedding")
    assert len(post.requests) == 1
    assert json.loads(post.requests[0].body)["payload"]["texts"] == ["a", "b"]


def test_completed_job_normalizes_embeddings():
    post = Transport(
        (
            200,
            {
                **job("completed"),
                "model": "document-embeddings",
                "result": {"embeddings": [[1, 2]]},
            },
        )
    )
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    assert provider.get_result("document-embeddings", "abc123", model_type="embedding") == [
        [1.0, 2.0]
    ]


def test_failed_job_raises_without_exposing_backend_diagnostics():
    post = Transport((200, job("failed", error={"message": "private document"})))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(InferenceError) as caught:
        provider.get_result("ocr", "abc123")
    assert caught.value.code == "gateway_job_failed"
    assert "private document" not in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [
        {"model": "other", "status": "completed"},
        {"model": "ocr", "status": "queued"},
        {"model": "ocr", "status": "running-unrecognized"},
        {"model": "ocr", "status": []},
    ],
)
def test_malformed_envelope_rejected(body):
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=Transport((202, body)))
    with pytest.raises(InferenceError):
        provider.submit("ocr", {})


def test_http_error_keeps_code_and_retry_hint_without_content():
    post = Transport((429, {"error": {"code": "backend_busy", "message": "private content"}}))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(GatewayHTTPError) as caught:
        provider.infer("ocr", {})
    assert caught.value.code == "backend_busy"
    assert caught.value.status_code == 429 and caught.value.retry_after == "5"
    assert "private content" not in str(caught.value)
    assert len(post.requests) == 1


def test_transport_failure_never_retries_or_echoes_credentials():
    requests = []

    def broken(request, *, timeout_seconds):
        requests.append(request)
        raise OSError("secret key and document")

    provider = InferenceGatewayProvider("https://gateway.test", post_fn=broken)
    with pytest.raises(InferenceError) as caught:
        provider.submit("ocr", {})
    assert caught.value.code == "gateway_transport_error"
    assert "secret" not in str(caught.value)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "url", ["", "file:///tmp/test", "https://user:key@host", "https://host?q=x"]
)
def test_bad_urls_rejected(url):
    with pytest.raises(ValueError):
        InferenceGatewayProvider(url)


def test_identifier_cannot_change_job_destination():
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=Transport())
    with pytest.raises(ValueError):
        provider.get_job("ocr", "../../secret")


def test_async_helpers_preserve_job_semantics():
    post = Transport((202, job()), (200, job("completed", result={"text": "Done"})))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)

    async def run():
        submitted = await provider.asubmit("ocr", {})
        return await provider.aget_result("ocr", submitted["job_id"])

    assert asyncio.run(run())["text"] == "Done"


def test_async_infer_and_stream_fallback_use_completed_text():
    post = Transport((200, completed(text="Done")), (200, completed(text="Done")))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    assert asyncio.run(provider.ainfer("query", "hello"))["text"] == "Done"
    assert list(provider.infer_stream("query", "hello")) == ["Done"]


def test_default_transport_sends_auth_and_disables_redirects(monkeypatch):
    class Response(io.BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://gateway.test/infer"
            assert request.headers["Authorization"] == "Bearer secret"
            return Response(json.dumps(completed(text="Done")).encode())

    def build_opener(handler):
        assert handler.redirect_request(None, None, 302, "redirect", {}, "https://other") is None
        return Opener()

    monkeypatch.setattr("urllib.request.build_opener", build_opener)
    assert (
        InferenceGatewayProvider("https://gateway.test", api_key="secret").infer(
            "query",
            "hello",
        )["text"]
        == "Done"
    )


def test_default_transport_preserves_http_status_without_echoing_body(monkeypatch):
    class Opener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "private diagnostic",
                {},
                io.BytesIO(b"private content"),
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Opener())
    with pytest.raises(GatewayHTTPError) as caught:
        InferenceGatewayProvider("https://gateway.test").infer("query", "hello")
    assert caught.value.status_code == 401
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("raw", [b"not-json", b"[]"])
def test_invalid_json_or_nonobject_response_rejected(raw):
    def post(request, *, timeout_seconds):
        return 200, raw, {}

    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(InferenceError):
        provider.infer("query", "hello")


def test_wrong_job_id_and_completed_job_without_result_rejected():
    post = Transport((200, job("completed")), (200, job("pending", job_id="other")))
    provider = InferenceGatewayProvider("https://gateway.test", post_fn=post)
    with pytest.raises(InferenceError, match="missing its result"):
        provider.get_result("ocr", "abc123")
    with pytest.raises(InferenceError, match="different job ID"):
        provider.get_job("ocr", "abc123")
