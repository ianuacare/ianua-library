"""Edge-case coverage for AI normalizer, speech provider, diarization, pause parser."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from typing import Any

from ianuacare.ai.models.inference.clusterer import SpeakerClusterer
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


def test_speech_transcription_groq_client_defaults_to_groq_base_url() -> None:
    client = SpeechTranscriptionProvider._build_client("groq", "gsk_test_key")
    assert client is not None
    assert str(client.base_url).rstrip("/") == "https://api.groq.com/openai/v1"


def test_speech_transcription_explicit_base_url_overrides_provider_default() -> None:
    client = SpeechTranscriptionProvider._build_client(
        "groq", "gsk_test_key", "https://custom.proxy.example/v1"
    )
    assert client is not None
    assert str(client.base_url).rstrip("/") == "https://custom.proxy.example/v1"


def test_speech_transcription_rejects_unsupported_provider() -> None:
    assert SpeechTranscriptionProvider._build_client("replicate", "some-key") is None


def _write_dummy_audio(tmp_path: Any) -> str:
    path = tmp_path / "sample.wav"
    path.write_bytes(b"RIFF....WAVEfmt ")
    return str(path)


def test_speech_transcription_sends_temperature_and_explicit_granularities(tmp_path: Any) -> None:
    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(text="hi", segments=[], words=[])
    provider = SpeechTranscriptionProvider(client=client, model="whisper-large-v3")

    provider.infer(
        "whisper-large-v3",
        {
            "audio_path": _write_dummy_audio(tmp_path),
            "response_format": "verbose_json",
            "temperature": 0.7,
            "timestamp_granularities": ["segment"],
        },
    )

    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "whisper-large-v3"
    assert kwargs["temperature"] == 0.7
    assert kwargs["timestamp_granularities"] == ["segment"]


def test_speech_transcription_omits_words_when_granularity_is_segment_only(tmp_path: Any) -> None:
    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(
        text="hi",
        segments=[MagicMock(start=0.0, end=1.0, text="hi")],
        # Simulates a provider that returns word data regardless; our code must
        # still honor the requested (segment-only) granularity and drop it.
        words=[MagicMock(start=0.0, end=0.5, word="hi")],
    )
    provider = SpeechTranscriptionProvider(client=client, model="whisper-large-v3")

    result = provider.infer(
        "whisper-large-v3",
        {"audio_path": _write_dummy_audio(tmp_path), "timestamp_granularities": ["segment"]},
    )
    assert result["words"] == []
    assert len(result["segments"]) == 1


def test_speech_transcription_legacy_word_timestamps_flag_still_works(tmp_path: Any) -> None:
    """Backward compatibility: payloads built before ``timestamp_granularities``
    existed only set the ``word_timestamps`` boolean."""
    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(text="hi", segments=[], words=[])
    provider = SpeechTranscriptionProvider(client=client, model="whisper-1")

    provider.infer(
        "whisper-1",
        {"audio_path": _write_dummy_audio(tmp_path), "word_timestamps": True},
    )

    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["timestamp_granularities"] == ["word", "segment"]


def test_speech_transcription_constructor_temperature_is_default(tmp_path: Any) -> None:
    client = MagicMock()
    client.audio.transcriptions.create.return_value = MagicMock(text="hi", segments=[], words=[])
    provider = SpeechTranscriptionProvider(client=client, model="whisper-1", temperature=0.2)

    provider.infer("whisper-1", {"audio_path": _write_dummy_audio(tmp_path)})
    assert client.audio.transcriptions.create.call_args.kwargs["temperature"] == 0.2

    # Per-call payload temperature takes precedence over the constructor default.
    provider.infer(
        "whisper-1", {"audio_path": _write_dummy_audio(tmp_path), "temperature": 0.9}
    )
    assert client.audio.transcriptions.create.call_args.kwargs["temperature"] == 0.9


class _StubSpeakerEmbedder:
    def run(self, payload: Any) -> list[list[float]]:
        segments = payload.get("segments", [])
        return [[1.0, 0.0] for _ in segments]


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
        embedder=_StubSpeakerEmbedder(),
        clusterer=SpeakerClusterer(),
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
    parser = PauseParser(silence_gap_seconds=1.5, merge_gaps=True)
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
