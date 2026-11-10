"""Tests for SpeakerEmbedder payload validation and MFCC embedding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ianuacare.ai.models.inference.embedder import SpeakerEmbedder, _mfcc_vector
from ianuacare.core.exceptions.errors import ValidationError


def test_run_requires_audio_path() -> None:
    with pytest.raises(ValidationError, match="audio_path"):
        SpeakerEmbedder().run({"start": 0.0, "end": 1.0})


def test_run_requires_mapping() -> None:
    with pytest.raises(ValidationError):
        SpeakerEmbedder().run("invalid")


def test_mfcc_vector_returns_normalized_length() -> None:
    sr = 16_000
    y = np.sin(np.linspace(0, 4 * np.pi, sr)).astype(np.float32)
    vector = _mfcc_vector(y, sr=sr, n_mfcc=20, include_delta=True)
    assert len(vector) == 80  # mean+std for mfcc and delta (20 * 4)
    assert all(isinstance(v, float) for v in vector)


def test_embed_segments_with_mocked_librosa() -> None:
    sr = 16_000
    y = np.random.default_rng(0).standard_normal(sr * 3).astype(np.float32)

    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (y, sr)
    mock_librosa.feature.mfcc.return_value = np.ones((20, 10))
    mock_librosa.feature.delta.return_value = np.zeros((20, 10))

    with patch(
        "ianuacare.ai.models.inference.embedder.import_module",
        side_effect=lambda name: mock_librosa if name == "librosa" else __import__(name),
    ):
        vectors = SpeakerEmbedder().run(
            {
                "audio_path": "/fake/audio.wav",
                "segments": [
                    {"start": 0.0, "end": 1.0},
                    {"start": 1.0, "end": 2.0},
                ],
            }
        )

    assert len(vectors) == 2
    assert len(vectors[0]) == 80


def test_load_waveform_drops_previous_file_before_decoding_the_next() -> None:
    sr = 16_000
    y = np.zeros(sr * 2, dtype=np.float32)
    embedder = SpeakerEmbedder()
    cached_at_load: list[int] = []

    def _load(*args: object, **kwargs: object) -> tuple[np.ndarray, int]:
        cached_at_load.append(len(embedder._waveform_cache))
        return (y, sr)

    mock_librosa = MagicMock()
    mock_librosa.load.side_effect = _load
    mock_librosa.feature.mfcc.return_value = np.ones((20, 10))
    mock_librosa.feature.delta.return_value = np.zeros((20, 10))

    with patch(
        "ianuacare.ai.models.inference.embedder.import_module",
        side_effect=lambda name: mock_librosa if name == "librosa" else __import__(name),
    ):
        embedder.run({"audio_path": "/fake/a.wav", "start": 0.0, "end": 1.0})
        embedder.run({"audio_path": "/fake/b.wav", "start": 0.0, "end": 1.0})

    assert cached_at_load == [0, 0]
    assert list(embedder._waveform_cache) == ["/fake/b.wav"]
    embedder.clear_cache()
    assert embedder._waveform_cache == {}
