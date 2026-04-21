"""LLM model built on top of NLP provider + normalizer."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider


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
        raw = self._provider.infer(self._model_name, payload)
        return self._normalizer.normalize_summary(raw)

    def stream(self, payload: Any) -> Iterator[str]:
        """Yield raw text fragments from the provider stream."""
        yield from self._provider.infer_stream(self._model_name, payload)

    async def arun(self, payload: Any) -> dict[str, Any]:
        raw = await self._provider.ainfer(self._model_name, payload)
        return self._normalizer.normalize_summary(raw)

    async def astream(self, payload: Any) -> AsyncIterator[str]:
        async for chunk in self._provider.ainfer_stream(self._model_name, payload):
            yield chunk

    def finalize_stream_text(self, text: str) -> dict[str, Any]:
        """Normalize assembled streaming output the same way as :meth:`run`."""
        return self._normalizer.normalize_summary({"text": text})
