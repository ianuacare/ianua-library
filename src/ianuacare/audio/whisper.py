"""Whisper transcription wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WhisperSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class WhisperResult:
    text: str
    segments: list[WhisperSegment]


class WhisperTranscriber:
    """Thin wrapper around OpenAI audio transcriptions API."""

    def __init__(self, client: Any | None = None, model: str = "whisper-1") -> None:
        self._client = client
        self._model = model

    def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
        response_format: str = "verbose_json",
    ) -> WhisperResult:
        if self._client is None:
            # Fallback for environments without openai[audio] configured.
            return WhisperResult(text="", segments=[])

        with open(audio_path, "rb") as f:
            resp = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                language=language,
                response_format=response_format,
            )
        segments: list[WhisperSegment] = []
        raw_segments = getattr(resp, "segments", None) or []
        for seg in raw_segments:
            start = float(getattr(seg, "start", 0.0))
            end = float(getattr(seg, "end", start))
            text = str(getattr(seg, "text", "")).strip()
            segments.append(WhisperSegment(start=start, end=end, text=text))
        full_text = str(getattr(resp, "text", "")).strip()
        return WhisperResult(text=full_text, segments=segments)
