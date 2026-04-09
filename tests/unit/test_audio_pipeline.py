"""Audio pipeline unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from ianuacare.ai.audio import DiarizationPipeline, SummaryGenerator, WhisperResult, WhisperSegment


def test_diarization_pipeline_returns_segments() -> None:
    transcriber = MagicMock()
    transcriber.transcribe.return_value = WhisperResult(
        text="hello world",
        segments=[
            WhisperSegment(start=0.0, end=1.2, text="hello"),
            WhisperSegment(start=1.4, end=2.1, text="world"),
        ],
    )
    out = DiarizationPipeline(transcriber=transcriber).run("/tmp/audio.wav", num_speakers=2)
    assert out.raw_transcription == "hello world"
    assert len(out.segments) == 2
    assert "speaker_id" in out.segments[0]


def test_summary_generator_fallback() -> None:
    result = SummaryGenerator(provider=None).generate(
        segments=[{"speaker_id": 0, "text": "A"}, {"speaker_id": 1, "text": "B"}],
        context={"session_id": "ses_1"},
    )
    assert result.text
    assert len(result.key_points) >= 1


def test_default_pipeline_uses_null_transcriber() -> None:
    out = DiarizationPipeline().run("/nonexistent-for-mock.wav", num_speakers=2)
    assert out.raw_transcription == ""
    assert out.segments == []
