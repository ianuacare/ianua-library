"""AudioEmotionModel and emotion normalizer."""

from __future__ import annotations

import pytest

from ianuacare.ai.models.inference.audio_emotion import AudioEmotionModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.exceptions.errors import InferenceError


def test_audio_emotion_model_run() -> None:
    provider = CallableProvider(
        infer_fn=lambda _m, _p: [[0.5460754, 0.6062266, 0.40431657]],
    )
    model = AudioEmotionModel(provider, "emotion-msp", ModelOutNormalizer())
    out = model.run({"audio_path": "/tmp/session.wav"})
    assert out["arousal"] == pytest.approx(0.5460754)
    assert out["dominance"] == pytest.approx(0.6062266)
    assert out["valence"] == pytest.approx(0.40431657)


def test_normalize_audio_emotion_from_dict() -> None:
    out = ModelOutNormalizer().normalize_audio_emotion(
        {"arousal": 0.5, "dominance": 0.6, "valence": 0.4}
    )
    assert out == {"arousal": 0.5, "dominance": 0.6, "valence": 0.4}


def test_normalize_audio_emotion_from_flat_list() -> None:
    out = ModelOutNormalizer().normalize_audio_emotion([0.1, 0.2, 0.3])
    assert out == {"arousal": 0.1, "dominance": 0.2, "valence": 0.3}


def test_normalize_audio_emotion_from_hf_labels() -> None:
    out = ModelOutNormalizer().normalize_audio_emotion(
        [
            {"label": "Arousal", "score": 0.54},
            {"label": "dominance", "score": 0.61},
            {"label": "VALENCE", "score": 0.40},
        ]
    )
    assert out["arousal"] == pytest.approx(0.54)
    assert out["dominance"] == pytest.approx(0.61)
    assert out["valence"] == pytest.approx(0.40)


def test_normalize_audio_emotion_rejects_unknown_format() -> None:
    with pytest.raises(InferenceError, match="not recognized"):
        ModelOutNormalizer().normalize_audio_emotion({"unexpected": 1})
