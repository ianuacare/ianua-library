"""Tests for SpeakerClusterer (K-Means clustering)."""

from __future__ import annotations

import pytest

from ianuacare.ai.models.inference.clusterer import DEFAULT_NUM_SPEAKERS, SpeakerClusterer

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


def test_defaults_to_two_clusters_for_separated_groups() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.95, 0.05, 0.0],
        [0.0, 1.0, 0.0],
        [0.05, 0.95, 0.0],
    ]
    labels = SpeakerClusterer().run({"vectors": vectors})
    assert len(labels) == 4
    assert len(set(labels)) == 2
    assert DEFAULT_NUM_SPEAKERS == 2


def test_single_vector_returns_one_label() -> None:
    labels = SpeakerClusterer().run({"vectors": [[1.0, 2.0, 3.0]]})
    assert labels == [0]


def test_empty_vectors_map_to_speaker_zero() -> None:
    labels = SpeakerClusterer().run({"vectors": [[], [1.0, 0.0]]})
    assert labels == [0, 0]


def test_invalid_num_speakers_falls_back_to_default() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.95, 0.05, 0.0],
        [0.0, 1.0, 0.0],
        [0.05, 0.95, 0.0],
    ]
    labels = SpeakerClusterer().run({"vectors": vectors, "num_speakers": "not-a-number"})
    assert len(labels) == 4
    assert len(set(labels)) == 2


def test_constructor_num_speakers_used_when_payload_omits_k() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.95, 0.05],
        [0.0, 0.0, 1.0],
        [0.05, 0.05, 0.9],
    ]
    labels = SpeakerClusterer(num_speakers=3).run({"vectors": vectors})
    assert len(labels) == 6
    assert len(set(labels)) == 3
