"""Speaker embedding model."""

from __future__ import annotations

from math import sqrt
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel


class SpeakerEmbedder(BaseAIModel):
    """Build deterministic vectors from segment features."""

    def run(self, payload: Any) -> list[float]:
        if not isinstance(payload, dict):
            return [0.0, 0.0, 0.0, 0.0, 0.0]

        duration = float(payload.get("duration", 0.0))
        tokens = float(payload.get("tokens", 0.0))
        chars = float(payload.get("chars", 0.0))
        rate = float(payload.get("rate", 0.0))
        return [duration, tokens, chars, rate, sqrt(tokens * max(duration, 0.0))]
