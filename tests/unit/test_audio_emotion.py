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


def test_batch_weighted_mean_and_filter(monkeypatch):
    from ianuacare.ai.models.inference import audio_emotion

    def clips(audio, segments, **kwargs):
        assert segments == [
            {"start": 0.0, "end": 2.0},
            {"start": 3.0, "end": 7.0},
            {"start": 8.0, "end": 8.5},
        ]
        for s in segments:
            yield {**s, "duration": s["end"] - s["start"], "audio_bytes": b"clip"}

    monkeypatch.setattr(audio_emotion, "iter_segment_clips", clips)
    scores = iter([[0, 0.2, 0.4], [0.9, 0.8, 0.7]])
    calls = []

    def infer(_m, payload):
        calls.append(payload)
        return next(scores)

    model = AudioEmotionModel(
        CallableProvider(infer_fn=infer), "wavlm-emotion", ModelOutNormalizer()
    )
    result = model.run(
        {
            "audio_bytes": b"audio",
            "speaker_id": 1,
            "segments": [
                {"start": 0, "end": 2, "speaker_id": 1},
                {"start": 2, "end": 3, "speaker_id": 0},
                {"start": 3, "end": 7, "speaker_id": 1},
                {"start": 8, "end": 8.5, "speaker_id": 1},
            ],
        }
    )
    assert result["mean"] == pytest.approx({"arousal": 0.6, "dominance": 0.6, "valence": 0.6})
    assert result["arousal"] == result["mean"]["arousal"]
    assert result["segment_count"] == len(calls) == 2
    assert result["skipped"][0]["reason"] == "below_min_clip_seconds"


@pytest.mark.parametrize(
    "payload",
    [
        {"segments": []},
        {"segments": [], "speaker_id": 1},
        {"segments": None, "speaker_id": 1},
        {"segments": [{"start": 0, "end": 1, "speaker_id": 0}], "speaker_id": 1},
        {"segments": [], "speaker_id": 1, "min_clip_seconds": float("nan")},
    ],
)
def test_batch_validation(payload):
    from ianuacare.core.exceptions.errors import ValidationError

    model = AudioEmotionModel(CallableProvider(), "wavlm-emotion", ModelOutNormalizer())
    with pytest.raises(ValidationError):
        model.run(payload)


def test_server_envelope_normalizer():
    assert ModelOutNormalizer().normalize_audio_emotion(
        {
            "scores": {
                "arousal": 0.2,
                "dominance": 0.4,
                "valence": 0.6,
            }
        }
    ) == {"arousal": 0.2, "dominance": 0.4, "valence": 0.6}


def test_batch_merge_and_skip_all(monkeypatch):
    from ianuacare.ai.models.inference import audio_emotion
    from ianuacare.core.exceptions.errors import ValidationError

    def clips(audio, segments, **kwargs):
        assert segments == [{"start": 0.0, "end": 0.8}, {"start": 1.0, "end": 1.2}]
        for s in segments:
            yield {**s, "duration": s["end"] - s["start"], "audio_bytes": b"clip"}

    monkeypatch.setattr(audio_emotion, "iter_segment_clips", clips)
    model = AudioEmotionModel(CallableProvider(), "wavlm-emotion", ModelOutNormalizer())
    with pytest.raises(ValidationError, match="No segments survive"):
        model.run(
            {
                "audio_bytes": b"audio",
                "speaker_id": 1,
                "merge_consecutive": True,
                "segments": [
                    {"start": 0, "end": 0.4, "speaker_id": 1},
                    {"start": 0.4, "end": 0.8, "speaker_id": 1},
                    {"start": 1, "end": 1.2, "speaker_id": 1},
                ],
            }
        )


def test_real_batch_splits_and_weights(tmp_path):
    import io

    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    path = tmp_path / "audio.wav"
    sf.write(path, np.zeros(16000 * 5), 16000)
    durations = []

    def infer(_model, payload):
        info = sf.info(io.BytesIO(payload["audio_bytes"]))
        durations.append(info.duration)
        return {"scores": {"arousal": info.duration, "dominance": 0.5, "valence": 0.2}}

    model = AudioEmotionModel(
        CallableProvider(infer_fn=infer),
        "wavlm-emotion",
        ModelOutNormalizer(),
        max_clip_seconds=2,
    )
    out = model.run(
        {
            "audio_path": str(path),
            "speaker_id": 1,
            "segments": [{"start": 0, "end": 4.5, "speaker_id": 1}],
        }
    )
    assert durations == [2, 2]
    assert out["arousal"] == 2
    assert out["segment_count"] == 2
    assert out["skipped"][0]["duration"] == 0.5
