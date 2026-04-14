"""NLP model base implementation."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.providers.base import AIProvider


class NLPModel(BaseAIModel):
    """Routes inference through an :class:`AIProvider` and fixed model name."""

    def __init__(self, provider: AIProvider, model_name: str) -> None:
        self._provider = provider
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def run(self, payload: Any) -> Any:
        return self._provider.infer(self._model_name, payload)
