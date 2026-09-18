"""Self-hosted text embedding provider speaking the ianua models server contract."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from ianuacare.ai.providers.base import AIProvider
from ianuacare.ai.providers.rest_hosted import PostFn, RestHostedModelProvider, RestRequest
from ianuacare.core.exceptions.errors import InferenceError

_EMBEDDING_MODEL_TYPES = (None, "embedding", "embeddings")
_DEFAULT_BATCH_SIZE = 32


def _build_request(model_name: str, payload: Any) -> RestRequest:
    return RestRequest(
        headers={"Content-Type": "application/json"},
        body=json.dumps({"model": model_name, "payload": payload}).encode("utf-8"),
    )


def _parse_response(
    status_code: int,
    body: bytes,
    *,
    headers: Mapping[str, str],
) -> list[list[float]]:
    _ = headers
    if status_code < 200 or status_code >= 300:
        raise InferenceError(f"embedding endpoint returned status {status_code}")
    try:
        data = json.loads(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InferenceError("embedding endpoint returned non-JSON body") from exc

    vectors = data.get("embeddings") if isinstance(data, dict) else None
    if not isinstance(vectors, list):
        raise InferenceError("embedding response is missing the embeddings key")

    dimension = len(vectors[0]) if vectors and isinstance(vectors[0], list) else 0
    for index, vector in enumerate(vectors):
        if not isinstance(vector, list) or not vector or len(vector) != dimension:
            raise InferenceError(f"embedding vector at index {index} has an inconsistent size")
        for component in vector:
            if isinstance(component, bool) or not isinstance(component, (int, float)):
                raise InferenceError(f"embedding vector at index {index} is not numeric")
            if not math.isfinite(component):
                raise InferenceError(f"embedding vector at index {index} is not finite")
    return [[float(component) for component in vector] for vector in vectors]


class SelfHostedEmbeddingProvider(AIProvider):
    """Embed text batches through a self-hosted REST endpoint.

    Translates the ordered ``list[str]`` batch produced by
    :class:`ianuacare.ai.models.inference.TextEmbedder` into bounded
    ``{"model": ..., "payload": {"texts": [...]}}`` requests and returns the
    ``embeddings`` list, preserving input order across batches.

    Constructor options act as request defaults; per-call ``params`` override
    them. ``instruction`` is only sent for ``input_type="query"``, since the
    endpoint rejects it for documents.
    """

    def __init__(
        self,
        endpoint_url: str,
        *,
        api_key: str | None = None,
        input_type: str = "document",
        instruction: str | None = None,
        dimensions: int | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        timeout_seconds: float = 600.0,
        post_fn: PostFn | None = None,
    ) -> None:
        if input_type not in ("document", "query"):
            raise ValueError("input_type must be document or query")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self._batch_size = batch_size
        self._defaults: dict[str, Any] = {"input_type": input_type}
        if instruction is not None and input_type == "query":
            self._defaults["instruction"] = instruction
        if dimensions is not None:
            self._defaults["dimensions"] = dimensions
        self._rest = RestHostedModelProvider(
            endpoint_url,
            api_key=api_key,
            build_request=_build_request,
            parse_response=_parse_response,
            post_fn=post_fn,
            timeout_seconds=timeout_seconds,
        )

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        if model_type not in _EMBEDDING_MODEL_TYPES:
            raise ValueError("SelfHostedEmbeddingProvider only supports embedding requests")

        texts = [payload] if isinstance(payload, str) else payload
        if not isinstance(texts, list) or not all(
            isinstance(text, str) and text.strip() for text in texts
        ):
            raise ValueError("embedding payload must be a string or a list of non-empty strings")

        request_params = {**self._defaults, **(params or {})}
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            result = self._rest.infer(model_name, {"texts": batch}, params=request_params)
            if len(result) != len(batch):
                raise InferenceError("embedding response vector count does not match the batch")
            if vectors and result and len(vectors[0]) != len(result[0]):
                raise InferenceError("embedding dimension changed between batches")
            vectors.extend(result)
        return vectors
