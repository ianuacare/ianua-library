"""Audio workflow unit tests."""

from __future__ import annotations

from ianuacare.ai.models.inference.diarization import DiarizationModel
from ianuacare.ai.models.inference.LLM import LLMModel
from ianuacare.ai.models.inference.transcription import Transcription
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.providers.callable import CallableProvider


def test_diarization_model_returns_segments() -> None:
    provider = CallableProvider(
        infer_fn=lambda model_name, payload: {
            "text": "hello world",
            "segments": [
                {"start": 0.0, "end": 1.2, "text": "hello"},
                {"start": 1.4, "end": 2.1, "text": "world"},
            ],
        }
    )
    transcription = Transcription(
        provider=provider,
        model_name="asr",
        normalizer=ModelOutNormalizer(),
    )
    out = DiarizationModel(
        transcription=transcription,
        pause_parser=PauseParser(silence_gap_seconds=0.1),
    ).run({"audio_path": "/tmp/audio.wav"})
    assert out["raw_transcription"] == "hello world"
    assert len(out["segments"]) == 2
    assert "speaker_id" in out["segments"][0]


def test_llm_model_with_normalizer() -> None:
    provider = CallableProvider(
        infer_fn=lambda model_name, payload: {
            "text": "- point A\n- point B",
        }
    )
    result = LLMModel(
        provider=provider,
        model_name="summary",
        normalizer=ModelOutNormalizer(),
    ).run({"segments": [{"speaker_id": 0, "text": "A"}]})
    assert result["text"]
    assert len(result["key_points"]) >= 1


def test_default_diarization_without_transcription() -> None:
    out = DiarizationModel().run({"audio_path": "/nonexistent-for-mock.wav", "num_speakers": 2})
    assert out["raw_transcription"] == ""
    assert out["segments"] == []
