"""Tests for TopicClusterer."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference.topic_clusterer import TOPIC_CLUSTERS, TopicClusterer
from ianuacare.core.exceptions.errors import ValidationError


class _FakeTextEmbedder:
    """Return deterministic sentence embeddings for topic anchors."""

    def run(self, payload: Any) -> dict[str, Any]:
        assert isinstance(payload, dict)
        sentences = payload.get("sentences", [])
        assert isinstance(sentences, list)
        vectors: list[list[float]] = []
        for index, sentence in enumerate(sentences):
            assert isinstance(sentence, str)
            base = float((sum(ord(ch) for ch in sentence) % 11) + 1)
            vectors.append([base + float(index), base / 3.0, base / 5.0])
        return {"sentence_vect": vectors}


def test_run_returns_ranked_clusters_and_examples() -> None:
    model = TopicClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    payload = {
        "vectors": [
            [0.0, 0.2, 0.0],
            [0.1, 0.1, 0.1],
            [0.2, 0.0, 0.1],
            [4.9, 5.0, 5.1],
            [5.1, 5.0, 4.9],
        ],
        "texts": [
            "Conflitto con i genitori in famiglia",
            "Parlo con mio padre e madre del lavoro",
            "Mi sento solo nel gruppo di amici",
            "Stress in azienda e carriera bloccata",
            "Colleghi e burnout sul lavoro",
        ],
        "num_clusters": 2,
    }

    result = model.run(payload)

    assert len(result["labels"]) == 5
    assert len(result["topics"]) == 5
    assert len(result["cluster_to_topic"]) == 2
    assert all(topic in TOPIC_CLUSTERS for topic in result["topics"])
    assert len(result["ranked_clusters"]) == 2
    assert result["ranked_clusters"][0]["count"] >= result["ranked_clusters"][1]["count"]
    assert 0.0 <= result["ranked_clusters"][0]["percentage"] <= 1.0
    assert len(result["ranked_clusters"][0]["examples"]) <= 5
    assert isinstance(result["ranked_clusters"][0]["keywords"], list)


@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        {},
        {"vectors": []},
        {"vectors": [1, 2, 3]},
        {"vectors": [[1.0, 2.0], [1.0]], "texts": ["a", "b"]},
        {"vectors": [[1.0, 2.0]], "texts": [1]},
        {"vectors": [[1.0, 2.0]], "texts": ["a", "b"]},
        {"vectors": [[1.0, "x"]]},
        {"vectors": [[1.0, 2.0]], "num_clusters": 0},
    ],
)
def test_run_rejects_invalid_payload(payload: Any) -> None:
    model = TopicClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    with pytest.raises(ValidationError):
        model.run(payload)
