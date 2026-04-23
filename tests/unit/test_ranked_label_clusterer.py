"""Tests for RankedLabelClusterer."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference.ranked_label_clusterer import RankedLabelClusterer
from ianuacare.core.exceptions.errors import ValidationError

LABEL_CLUSTERS = {
    "relazioni_familiari": ["famiglia", "genitori", "fratelli"],
    "lavoro_e_carriera": ["lavoro", "carriera", "azienda"],
    "amicizie_e_rete_sociale": ["amicizia", "gruppo", "supporto"],
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
            base = float((sum(ord(ch) for ch in sentence) % 11) + 1)
            vectors.append([base + float(index), base / 3.0, base / 5.0])
        return {"sentence_vect": vectors}


def test_run_returns_ranked_clusters_and_examples() -> None:
    model = RankedLabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
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
        "label_clusters": LABEL_CLUSTERS,
    }

    result = model.run(payload)

    assert len(result["labels"]) == 5
    assert len(result["assigned_labels"]) == 5
    assert len(result["cluster_to_label"]) == 2
    assert all(item in LABEL_CLUSTERS for item in result["assigned_labels"])
    assert len(result["ranked_clusters"]) == 2
    assert result["ranked_clusters"][0]["count"] >= result["ranked_clusters"][1]["count"]
    assert 0.0 <= result["ranked_clusters"][0]["percentage"] <= 1.0
    assert len(result["ranked_clusters"][0]["examples"]) <= 5
    assert isinstance(result["ranked_clusters"][0]["keywords"], list)
    assert result["texts"] == payload["texts"]
    assert result["point_ids"] == [None, None, None, None, None]


def test_run_echoes_point_ids() -> None:
    model = RankedLabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    payload = {
        "vectors": [
            [0.0, 0.2, 0.0],
            [4.9, 5.0, 5.1],
        ],
        "texts": ["a", "b"],
        "point_ids": ["p-0", 99],
        "num_clusters": 2,
        "label_clusters": LABEL_CLUSTERS,
    }

    result = model.run(payload)

    assert result["texts"] == ["a", "b"]
    assert result["point_ids"] == ["p-0", 99]
    assert len(result["labels"]) == 2


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
        {"vectors": [[1.0, "x"]], "label_clusters": LABEL_CLUSTERS},
        {"vectors": [[1.0, 2.0]], "num_clusters": 0, "label_clusters": LABEL_CLUSTERS},
        {"vectors": [[1.0, 2.0]], "label_clusters": {}},
        {"vectors": [[1.0, 2.0]], "label_clusters": {"x": []}},
        {"vectors": [[1.0, 2.0]], "label_clusters": LABEL_CLUSTERS, "stopwords": "bad"},
        {
            "vectors": [[1.0, 2.0], [1.0, 2.0]],
            "texts": ["x", "y"],
            "point_ids": [1],
            "label_clusters": LABEL_CLUSTERS,
        },
        {"vectors": [[1.0, 2.0]], "label_clusters": LABEL_CLUSTERS, "point_ids": "bad"},
    ],
)
def test_run_rejects_invalid_payload(payload: Any) -> None:
    model = RankedLabelClusterer(text_embedder=_FakeTextEmbedder(), random_state=0)
    with pytest.raises(ValidationError):
        model.run(payload)
