"""Tests for EmotionClusterer."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference.emotion_clusterer import (
    EMOTION_CLUSTERS,
    EmotionClusterer,
)
from ianuacare.core.exceptions.errors import ValidationError


class _FakeTextEmbedder:
    """Return deterministic sentence embeddings for emotion anchors."""

    def run(self, payload: Any) -> dict[str, Any]:
        assert isinstance(payload, dict)
        sentences = payload.get("sentences", [])
        assert isinstance(sentences, list)
        vectors: list[list[float]] = []
        for index, sentence in enumerate(sentences):
            assert isinstance(sentence, str)
            base = float((sum(ord(ch) for ch in sentence) % 13) + 1)
            vectors.append([base + float(index), base / 2.0, base / 3.0])
        return {"sentence_vect": vectors}


def test_run_clusters_and_maps_emotions() -> None:
    model = EmotionClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    payload = {
        "vectors": [
            [0.0, 0.1, 0.0],
            [0.1, 0.0, 0.1],
            [5.0, 5.1, 5.2],
            [5.2, 5.0, 5.1],
        ]
    }

    result = model.run(payload)

    assert len(result["labels"]) == 4
    assert len(result["emotions"]) == 4
    assert len(result["cluster_to_emotion"]) == min(4, len(EMOTION_CLUSTERS))
    assert all(emotion in EMOTION_CLUSTERS for emotion in result["emotions"])
    assert len(result["projected_vectors"]) == 4
    assert len(result["projected_vectors"][0]) == 2
    assert 1 <= len(result["explained_variance_ratio"]) <= 2


@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        {},
        {"vectors": []},
        {"vectors": [1, 2, 3]},
        {"vectors": [[1.0, 2.0], [1.0]]},
        {"vectors": [[1.0, "x"]]},
    ],
)
def test_run_rejects_invalid_payload(payload: Any) -> None:
    model = EmotionClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    with pytest.raises(ValidationError):
        model.run(payload)
