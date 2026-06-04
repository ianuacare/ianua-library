"""Dimensional speech emotion model (arousal, dominance, valence)."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider


class AudioEmotionModel(NLPModel):
    """Inference model for audio emotion recognition via a REST-hosted provider."""

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
        return self._normalizer.normalize_audio_emotion(raw)
