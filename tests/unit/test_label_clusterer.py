"""Tests for LabelClusterer."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference.label_clusterer import LabelClusterer
from ianuacare.core.exceptions.errors import ValidationError

LABEL_CLUSTERS = {
    "cluster_a": ["tristezza", "vuoto", "disperazione"],
    "cluster_b": ["ansia", "paura", "preoccupazione"],
    "cluster_c": ["gioia", "sollievo", "speranza"],
}


class _FakeTextEmbedder:
    """Return deterministic sentence embeddings for label anchors."""

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


def test_run_clusters_and_maps_labels() -> None:
    model = LabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    payload = {
        "vectors": [
            [0.0, 0.1, 0.0],
            [0.1, 0.0, 0.1],
            [5.0, 5.1, 5.2],
            [5.2, 5.0, 5.1],
        ],
        "label_clusters": LABEL_CLUSTERS,
    }

    result = model.run(payload)

    assert len(result["labels"]) == 4
    assert len(result["assigned_labels"]) == 4
    assert len(result["cluster_to_label"]) == min(4, len(LABEL_CLUSTERS))
    assert all(item in LABEL_CLUSTERS for item in result["assigned_labels"])
    assert len(result["projected_vectors"]) == 4
    assert len(result["projected_vectors"][0]) == 2
    assert 1 <= len(result["explained_variance_ratio"]) <= 2
    assert result["texts"] == ["", "", "", ""]
    assert result["point_ids"] == [None, None, None, None]


def test_run_echoes_texts_and_point_ids() -> None:
    model = LabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    payload = {
        "vectors": [
            [0.0, 0.1, 0.0],
            [5.0, 5.1, 5.2],
        ],
        "label_clusters": LABEL_CLUSTERS,
        "texts": ["alpha", "beta"],
        "point_ids": ["p-1", 42],
    }

    result = model.run(payload)

    assert result["texts"] == ["alpha", "beta"]
    assert result["point_ids"] == ["p-1", 42]
    assert len(result["labels"]) == 2


@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        {},
        {"vectors": []},
        {"vectors": [1, 2, 3]},
        {"vectors": [[1.0, 2.0], [1.0]], "label_clusters": LABEL_CLUSTERS},
        {"vectors": [[1.0, "x"]], "label_clusters": LABEL_CLUSTERS},
        {"vectors": [[1.0, 2.0]], "label_clusters": {}},
        {"vectors": [[1.0, 2.0]], "label_clusters": {"x": []}},
        {"vectors": [[1.0, 2.0], [1.0, 2.0]], "label_clusters": LABEL_CLUSTERS, "texts": ["a"]},
        {"vectors": [[1.0, 2.0]], "label_clusters": LABEL_CLUSTERS, "point_ids": []},
        {"vectors": [[1.0, 2.0]], "label_clusters": LABEL_CLUSTERS, "point_ids": [1, 2]},
    ],
)
def test_run_rejects_invalid_payload(payload: Any) -> None:
    model = LabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    with pytest.raises(ValidationError):
        model.run(payload)
