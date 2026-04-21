"""Together AI provider adapter."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

try:  # Optional dependency
    from together import Together
except Exception:  # pragma: no cover - optional import
    Together = None  # type: ignore[assignment]

from ianuacare.ai.providers.base import AIProvider


def _embedding_mode(model_type: str | None) -> bool:
    if model_type is None:
        return False
    mt = model_type.strip().lower()
    return mt in ("embedding", "embeddings")


class TogetherAIProvider(AIProvider):
    """Provider backed by Together chat completions and embeddings."""

    def __init__(self, api_key: str, default_model: str) -> None:
        if Together is None:
            raise ImportError("TogetherAIProvider requires together")
        self._client = Together(api_key=api_key)
        self._default_model = default_model

    def infer(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> Any:
        if _embedding_mode(model_type):
            return self._infer_embeddings(model_name, payload)
        return self._infer_chat(model_name, payload)

    def infer_stream(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> Iterator[str]:
        if _embedding_mode(model_type):
            raise TypeError("TogetherAIProvider does not stream embedding requests")
        yield from super().infer_stream(model_name, payload, model_type=model_type)

    def _infer_chat(self, model_name: str, payload: Any) -> dict[str, Any]:
        selected_model = model_name or self._default_model
        response = self._client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": str(payload)}],
        )
        choice = response.choices[0]
        return {
            "model": selected_model,
            "content": choice.message.content,
            "raw": response.model_dump(),
        }

    def _infer_embeddings(self, model_name: str, payload: Any) -> list[list[float]]:
        selected_model = model_name or self._default_model
        if isinstance(payload, str):
            inputs: str | list[str] = payload
        elif isinstance(payload, list) and all(isinstance(x, str) for x in payload):
            inputs = payload
        else:
            raise TypeError(
                "Together embedding payload must be str or list[str], got "
                f"{type(payload).__name__}"
            )
        response = self._client.embeddings.create(model=selected_model, input=inputs)
        rows = sorted(response.data or [], key=lambda row: row.index)
        return [list(row.embedding) for row in rows]
