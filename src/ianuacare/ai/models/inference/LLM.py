"""LLM model built on top of NLP provider + normalizer."""

from __future__ import annotations

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
