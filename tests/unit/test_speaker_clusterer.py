"""Tests for SpeakerClusterer (agglomerative + Silhouette k selection)."""

from __future__ import annotations

import pytest

from ianuacare.ai.models.inference.clusterer import SpeakerClusterer

pytest.importorskip("sklearn")


def test_fixed_num_speakers_two_clusters() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.95, 0.05],
    ]
    labels = SpeakerClusterer().run({"vectors": vectors, "num_speakers": 2})
    assert len(labels) == 4
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


def test_silhouette_selects_two_clusters_for_separated_groups() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.95, 0.05, 0.0],
        [0.0, 1.0, 0.0],
        [0.05, 0.95, 0.0],
    ]
    labels = SpeakerClusterer().run(
        {
            "vectors": vectors,
            "min_speakers": 2,
            "max_speakers": 4,
        }
    )
    assert len(labels) == 4
    assert len(set(labels)) == 2


def test_single_vector_returns_one_label() -> None:
    labels = SpeakerClusterer().run({"vectors": [[1.0, 2.0, 3.0]]})
    assert labels == [0]


def test_empty_vectors_map_to_speaker_zero() -> None:
    labels = SpeakerClusterer().run({"vectors": [[], [1.0, 0.0]]})
    assert labels == [0, 0]
