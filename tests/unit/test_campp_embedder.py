"""Tests for CamPlusPlusEmbedder payload validation and ONNX embedding."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ianuacare.ai.models.inference.campp_embedder import CamPlusPlusEmbedder
from ianuacare.core.exceptions.errors import InferenceError, ValidationError


def test_run_requires_audio_path() -> None:
    with pytest.raises(ValidationError, match="audio_path"):
        CamPlusPlusEmbedder().run({"start": 0.0, "end": 1.0})


def test_run_requires_mapping() -> None:
    with pytest.raises(ValidationError):
        CamPlusPlusEmbedder().run("invalid")


def test_missing_model_raises_inference_error() -> None:
    sr = 16_000
    y = np.random.default_rng(0).standard_normal(sr * 2).astype(np.float32)
    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (y, sr)
    with patch(
        "ianuacare.ai.models.inference.campp_embedder.import_module",
        side_effect=lambda name: mock_librosa if name == "librosa" else __import__(name),
    ):
        with pytest.raises(InferenceError, match="CAM\\+\\+ ONNX model not found"):
            CamPlusPlusEmbedder(model_path="/does/not/exist.onnx").run(
                {"audio_path": "/fake/audio.wav", "start": 0.0, "end": 1.0}
            )


def _mock_modules(y: np.ndarray, sr: int):
    """Build a fake import_module resolving librosa / kaldi_native_fbank / onnxruntime."""
    mock_librosa = MagicMock()
    mock_librosa.load.return_value = (y, sr)

    knf = MagicMock()
    fbank_instance = MagicMock()
    fbank_instance.num_frames_ready = 10
    fbank_instance.get_frame.side_effect = lambda i: np.ones(80, dtype=np.float32)
    knf.OnlineFbank.return_value = fbank_instance
    knf.FbankOptions.return_value = MagicMock()

    ort = MagicMock()
    session = MagicMock()
    inp = MagicMock()
    inp.name = "feats"
    session.get_inputs.return_value = [inp]
    session.run.return_value = [np.arange(192, dtype=np.float32).reshape(1, 192)]
    ort.InferenceSession.return_value = session

    registry = {"librosa": mock_librosa, "kaldi_native_fbank": knf, "onnxruntime": ort}

    def _resolve(name: str) -> Any:
        return registry[name] if name in registry else __import__(name)

    return _resolve


def test_embed_segments_returns_normalized_192(tmp_path) -> None:
    model = tmp_path / "campp.onnx"
    model.write_bytes(b"stub")  # only needs to exist; onnxruntime is mocked
    sr = 16_000
    y = np.random.default_rng(0).standard_normal(sr * 3).astype(np.float32)

    with patch(
        "ianuacare.ai.models.inference.campp_embedder.import_module",
        side_effect=_mock_modules(y, sr),
    ):
        vectors = CamPlusPlusEmbedder(model_path=str(model)).run(
            {
                "audio_path": "/fake/audio.wav",
                "segments": [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}],
            }
        )

    assert len(vectors) == 2
    assert len(vectors[0]) == 192
    assert vectors[0] and abs(sum(v * v for v in vectors[0]) - 1.0) < 1e-6  # L2-normalized


def test_short_segment_returns_empty(tmp_path) -> None:
    model = tmp_path / "campp.onnx"
    model.write_bytes(b"stub")
    sr = 16_000
    y = np.random.default_rng(0).standard_normal(sr * 2).astype(np.float32)

    with patch(
        "ianuacare.ai.models.inference.campp_embedder.import_module",
        side_effect=_mock_modules(y, sr),
    ):
        vectors = CamPlusPlusEmbedder(model_path=str(model), min_segment_seconds=0.5).run(
            {"audio_path": "/fake/audio.wav", "segments": [{"start": 0.0, "end": 0.1}]}
        )

    assert vectors == [[]]
