"""Audio workflow unit tests."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.clusterer import SpeakerClusterer
from ianuacare.ai.models.inference.diarization import DiarizationModel
from ianuacare.ai.models.inference.LLM import LLMModel
from ianuacare.ai.models.inference.transcription import Transcription
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.providers.callable import CallableProvider


class _StubSpeakerEmbedder:
    def run(self, payload: Any) -> list[list[float]]:
        segments = payload.get("segments", [])
        return [[float(index), 1.0 - float(index)] for index, _ in enumerate(segments)]


def test_diarization_splits_long_segments_before_clustering() -> None:
    provider = CallableProvider(
        infer_fn=lambda model_name, payload: {
            "text": "long",
            "segments": [{"start": 0.0, "end": 90.0, "text": "a b c d e f g h"}],
        }
    )
    transcription = Transcription(
        provider=provider,
        model_name="asr",
        normalizer=ModelOutNormalizer(),
    )

    class _AlternatingEmbedder:
        def run(self, payload: Any) -> list[list[float]]:
            segments = payload.get("segments", [])
            return [[1.0, 0.0] if index % 2 == 0 else [0.0, 1.0] for index, _ in enumerate(segments)]

    out = DiarizationModel(
        transcription=transcription,
        embedder=_AlternatingEmbedder(),
        clusterer=SpeakerClusterer(),
        max_segment_seconds=30.0,
    ).run({"audio_path": "/tmp/audio.wav", "num_speakers": 2})
    assert len(out["segments"]) >= 2


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
        embedder=_StubSpeakerEmbedder(),
        clusterer=SpeakerClusterer(),
    ).run({"audio_path": "/tmp/audio.wav", "num_speakers": 2})
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
    out = DiarizationModel(embedder=_StubSpeakerEmbedder()).run(
        {"audio_path": "/nonexistent-for-mock.wav", "num_speakers": 2}
    )
    assert out["raw_transcription"] == ""
    assert out["segments"] == []
