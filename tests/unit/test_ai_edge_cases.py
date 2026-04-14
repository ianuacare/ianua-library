"""Edge-case coverage for AI normalizer, speech provider, diarization, pause parser."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ianuacare.ai.models.inference.diarization import DiarizationModel
from ianuacare.ai.models.inference.transcription import Transcription
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.ai.providers.speech_transcription import SpeechTranscriptionProvider


def test_normalizer_tolerates_non_numeric_segment_times() -> None:
    out = ModelOutNormalizer().normalize_transcript(
        {
            "text": "x",
            "segments": [
                {"start": "not-a-number", "end": None, "text": "hello"},
            ],
        }
    )
    assert len(out["segments"]) == 1
    assert out["segments"][0]["start"] == 0.0
    assert out["segments"][0]["end"] == 0.0


def test_speech_transcription_rejects_missing_file() -> None:
    provider = SpeechTranscriptionProvider(client=MagicMock(), model="whisper-1")
    with pytest.raises(ValueError, match="not found|readable"):
        provider.infer("whisper-1", {"audio_path": "/nonexistent/ianuacare_missing_audio.wav"})


def test_diarization_accepts_invalid_num_speakers() -> None:
    stub = CallableProvider(
        infer_fn=lambda _m, _p: {
            "text": "a",
            "segments": [{"start": 0.0, "end": 1.0, "text": "x"}],
        }
    )
    transcription = Transcription(stub, "asr", ModelOutNormalizer())
    model = DiarizationModel(
        transcription=transcription,
        pause_parser=PauseParser(silence_gap_seconds=0.01),
    )
    out = model.run(
        {
            "audio_path": "/tmp/x.wav",
            "num_speakers": "not-a-number",
        }
    )
    assert "speakers" in out
    assert len(out["segments"]) >= 1


def test_pause_parser_merges_short_gaps() -> None:
    parser = PauseParser(silence_gap_seconds=1.5)
    out = parser.parse(
        [
            {"start": 0.0, "end": 1.0, "text": "a"},
            {"start": 1.2, "end": 2.0, "text": "b"},
        ]
    )
    assert len(out) == 1
    assert "a" in out[0]["text"]
    assert "b" in out[0]["text"]


def test_pause_parser_splits_long_gaps() -> None:
    parser = PauseParser(silence_gap_seconds=0.1)
    out = parser.parse(
        [
            {"start": 0.0, "end": 1.0, "text": "a"},
            {"start": 1.4, "end": 2.0, "text": "b"},
        ]
    )
    assert len(out) == 2
