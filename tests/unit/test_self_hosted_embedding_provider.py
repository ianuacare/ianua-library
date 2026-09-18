"""SelfHostedEmbeddingProvider."""

from __future__ import annotations

import json
from typing import Any

import pytest

from ianuacare.ai.models.inference import TextEmbedder
from ianuacare.ai.providers.rest_hosted import RestRequest
from ianuacare.ai.providers.self_hosted_embedding import SelfHostedEmbeddingProvider
from ianuacare.core.exceptions.errors import InferenceError


def _body(request: RestRequest) -> dict[str, Any]:
    assert request.body is not None
    return json.loads(request.body)


def _echo_post(captured: list[RestRequest], *, dimension: int = 2):
    """Return one vector per input text, recording every outbound request."""

    def post_fn(
        request: RestRequest, *, timeout_seconds: float
    ) -> tuple[int, bytes, dict[str, str]]:
        _ = timeout_seconds
        captured.append(request)
        texts = _body(request)["payload"]["texts"]
        vectors = [[float(index)] * dimension for index in range(len(texts))]
        return 200, json.dumps({"embeddings": vectors}).encode("utf-8"), {}

    return post_fn


class TestBatching:
    def test_splits_batches_and_preserves_order(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            batch_size=2,
            post_fn=_echo_post(captured),
        )
        vectors = provider.infer("qwen3-embedding", ["a", "b", "c", "d", "e"])
        assert len(captured) == 3
        assert [_body(r)["payload"]["texts"] for r in captured] == [["a", "b"], ["c", "d"], ["e"]]
        assert vectors == [[0.0, 0.0], [1.0, 1.0], [0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]

    def test_accepts_a_single_string(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer", post_fn=_echo_post(captured)
        )
        assert provider.infer("qwen3-embedding", "solo") == [[0.0, 0.0]]
        assert _body(captured[0])["payload"]["texts"] == ["solo"]

    def test_empty_batch_skips_http(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer", post_fn=_echo_post(captured)
        )
        assert provider.infer("qwen3-embedding", []) == []
        assert captured == []


class TestRequestDefaults:
    def test_sends_model_alias_and_constructor_defaults(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            dimensions=512,
            post_fn=_echo_post(captured),
        )
        provider.infer("qwen3-embedding", ["x"])
        body = _body(captured[0])
        assert body["model"] == "qwen3-embedding"
        assert body["payload"]["input_type"] == "document"
        assert body["payload"]["dimensions"] == 512

    def test_per_call_params_override_defaults(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            dimensions=512,
            post_fn=_echo_post(captured),
        )
        provider.infer(
            "qwen3-embedding", ["x"], params={"input_type": "query", "dimensions": 256}
        )
        payload = _body(captured[0])["payload"]
        assert payload["input_type"] == "query"
        assert payload["dimensions"] == 256
        assert payload["texts"] == ["x"]

    def test_instruction_sent_for_query_input_type(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            input_type="query",
            instruction="Trova i passaggi rilevanti",
            post_fn=_echo_post(captured),
        )
        provider.infer("qwen3-embedding", ["domanda"])
        payload = _body(captured[0])["payload"]
        assert payload["input_type"] == "query"
        assert payload["instruction"] == "Trova i passaggi rilevanti"

    def test_instruction_omitted_for_documents(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            instruction="ignorata",
            post_fn=_echo_post(captured),
        )
        provider.infer("qwen3-embedding", ["documento"])
        assert "instruction" not in _body(captured[0])["payload"]

    def test_sends_bearer_when_api_key_set(self) -> None:
        captured: list[RestRequest] = []
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            api_key="secret-token",
            post_fn=_echo_post(captured),
        )
        provider.infer("qwen3-embedding", ["x"])
        assert captured[0].headers["Authorization"] == "Bearer secret-token"


class TestValidation:
    def test_rejects_non_embedding_model_type(self) -> None:
        provider = SelfHostedEmbeddingProvider("https://embed.test/infer", post_fn=_echo_post([]))
        with pytest.raises(ValueError, match="embedding"):
            provider.infer("qwen3-embedding", ["x"], model_type="chat")

    def test_rejects_blank_texts(self) -> None:
        provider = SelfHostedEmbeddingProvider("https://embed.test/infer", post_fn=_echo_post([]))
        with pytest.raises(ValueError, match="non-empty"):
            provider.infer("qwen3-embedding", ["ok", "  "])

    def test_rejects_invalid_input_type(self) -> None:
        with pytest.raises(ValueError, match="input_type"):
            SelfHostedEmbeddingProvider("https://embed.test/infer", input_type="passage")

    def test_rejects_invalid_batch_size(self) -> None:
        with pytest.raises(ValueError, match="batch_size"):
            SelfHostedEmbeddingProvider("https://embed.test/infer", batch_size=0)


class TestResponseErrors:
    @staticmethod
    def _provider(status: int, body: bytes) -> SelfHostedEmbeddingProvider:
        return SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            post_fn=lambda _r, timeout_seconds=0: (status, body, {}),
        )

    def test_error_status_raises(self) -> None:
        with pytest.raises(InferenceError, match="503"):
            self._provider(503, b"busy").infer("qwen3-embedding", ["x"])

    def test_missing_embeddings_key_raises(self) -> None:
        with pytest.raises(InferenceError, match="embeddings key"):
            self._provider(200, b'{"model": "qwen3-embedding"}').infer("qwen3-embedding", ["x"])

    def test_inconsistent_dimensions_raise(self) -> None:
        body = b'{"embeddings": [[0.1, 0.2], [0.3]]}'
        with pytest.raises(InferenceError, match="inconsistent size"):
            self._provider(200, body).infer("qwen3-embedding", ["x", "y"])

    def test_non_numeric_components_raise(self) -> None:
        with pytest.raises(InferenceError, match="not numeric"):
            self._provider(200, b'{"embeddings": [["nope"]]}').infer("qwen3-embedding", ["x"])

    def test_vector_count_mismatch_raises(self) -> None:
        with pytest.raises(InferenceError, match="vector count"):
            self._provider(200, b'{"embeddings": [[0.1]]}').infer("qwen3-embedding", ["x", "y"])

    def test_dimension_change_between_batches_raises(self) -> None:
        bodies = [b'{"embeddings": [[0.1, 0.2]]}', b'{"embeddings": [[0.3]]}']
        provider = SelfHostedEmbeddingProvider(
            "https://embed.test/infer",
            batch_size=1,
            post_fn=lambda _r, timeout_seconds=0: (200, bodies.pop(0), {}),
        )
        with pytest.raises(InferenceError, match="dimension changed"):
            provider.infer("qwen3-embedding", ["x", "y"])


class TestTextEmbedderIntegration:
    def test_feeds_text_embedder_artefact(self) -> None:
        captured: list[RestRequest] = []
        embedder = TextEmbedder(
            provider=SelfHostedEmbeddingProvider(
                "https://embed.test/infer", post_fn=_echo_post(captured)
            ),
            model_name="qwen3-embedding",
        )
        result = embedder.run(
            {
                "id_artefatto_trascrizione": "tr-1",
                "text": "uno due",
                "chunks": ["uno", "due"],
                "sentences": ["uno due."],
                "words": [],
            }
        )
        assert [_body(r)["payload"]["texts"] for r in captured] == [["uno", "due", "uno due."]]
        assert result["chunks_vect"] == [[0.0, 0.0], [1.0, 1.0]]
        assert result["sentence_vect"] == [[2.0, 2.0]]
        assert result["text_vect"] == [0.5, 0.5]
