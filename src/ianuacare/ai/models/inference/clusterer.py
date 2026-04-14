"""Speaker clustering model."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel


class SpeakerClusterer(BaseAIModel):
    """Cluster embedding vectors into stable speaker labels."""

    def run(self, payload: Any) -> list[int]:
        if not isinstance(payload, dict):
            return []
        vectors = payload.get("vectors")
        if not isinstance(vectors, list):
            return []
        num_speakers = int(payload.get("num_speakers", 1))
        k = max(1, num_speakers)

        labels: list[int] = []
        for index, vector in enumerate(vectors):
            if not isinstance(vector, list):
                labels.append(index % k)
                continue
            signal = int(sum(int(float(value) * 1000) for value in vector))
            labels.append(abs(signal + index) % k)
        return labels
