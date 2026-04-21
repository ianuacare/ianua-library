"""LLM model built on top of NLP provider + normalizer."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider


def _payload_without_model_type(payload: Any) -> tuple[Any, str | None]:
    """Split optional ``model_type`` for routing (e.g. Together chat vs embeddings)."""
    if not isinstance(payload, dict):
        return payload, None
    mt = payload.get("model_type")
    if isinstance(mt, str) and mt.strip():
        trimmed = dict(payload)
        trimmed.pop("model_type", None)
        return trimmed, mt.strip().lower()
    return payload, None


class LLMModel(NLPModel):
    """Inference model for LLM text generation tasks."""

    def __init__(
        self,
        provider: AIProvider,
        model_name: str,
        normalizer: ModelOutNormalizer,
    ) -> None:
        super().__init__(provider, model_name)
        self._normalizer = normalizer

    def run(self, payload: Any) -> dict[str, Any]:
        body, model_type = _payload_without_model_type(payload)
        raw = self._provider.infer(self._model_name, body, model_type=model_type)
        return self._normalizer.normalize_summary(raw)

    def stream(self, payload: Any) -> Iterator[str]:
        """Yield raw text fragments from the provider stream."""
        body, model_type = _payload_without_model_type(payload)
        yield from self._provider.infer_stream(self._model_name, body, model_type=model_type)

    async def arun(self, payload: Any) -> dict[str, Any]:
        body, model_type = _payload_without_model_type(payload)
        raw = await self._provider.ainfer(self._model_name, body, model_type=model_type)
        return self._normalizer.normalize_summary(raw)

    async def astream(self, payload: Any) -> AsyncIterator[str]:
        body, model_type = _payload_without_model_type(payload)
        async for chunk in self._provider.ainfer_stream(self._model_name, body, model_type=model_type):
            yield chunk

    def finalize_stream_text(self, text: str) -> dict[str, Any]:
        """Normalize assembled streaming output the same way as :meth:`run`."""
        return self._normalizer.normalize_summary({"text": text})
