"""Pluggable speech-to-text (ASR) primitives and OpenAI-based implementation."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# OpenAI audio transcriptions API rejects payloads above ~25 MiB (error 413).
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# Margin for WAV header / float32→int16 rounding when writing temp files.
_SAFE_CHUNK_BYTES = 24 * 1024 * 1024


@dataclass(slots=True)
class WhisperSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class WhisperResult:
    text: str
    segments: list[WhisperSegment]


@runtime_checkable
class SpeechTranscriber(Protocol):
    """Protocol for file-based ASR used by :class:`DiarizationPipeline`."""

    def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
        response_format: str = "verbose_json",
    ) -> WhisperResult:
        """Return transcript text and time-aligned segments."""
        ...


class NullSpeechTranscriber:
    """No-op transcriber for tests or environments without ASR."""

    def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
        response_format: str = "verbose_json",
    ) -> WhisperResult:
        return WhisperResult(text="", segments=[])


class OpenAISpeechTranscriber:
    """OpenAI audio transcriptions API implementation of :class:`SpeechTranscriber`."""

    def __init__(self, client: Any | None = None, model: str = "whisper-1") -> None:
        self._client = client
        self._model = model

    def _transcribe_file_handle(
        self,
        f: Any,
        *,
        language: str | None,
        response_format: str,
    ) -> WhisperResult:
        assert self._client is not None
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

    @staticmethod
    def _max_samples_per_wav_chunk() -> int:
        """PCM16 mono on disk ≈ 2 * n_samples; keep under API size limit."""
        byte_budget = _SAFE_CHUNK_BYTES - 4096
        return max(1000, byte_budget // 2)

    def _transcribe_chunked(
        self,
        audio_path: str,
        *,
        language: str | None,
        response_format: str,
    ) -> WhisperResult:
        import librosa
        import soundfile as sf

        assert self._client is not None
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        n = int(len(y))
        if n == 0:
            return WhisperResult(text="", segments=[])

        max_samples = self._max_samples_per_wav_chunk()
        chunk_ranges: list[tuple[int, int]] = []
        start = 0
        while start < n:
            end = min(start + max_samples, n)
            chunk_ranges.append((start, end))
            start = end

        all_segments: list[WhisperSegment] = []
        text_parts: list[str] = []

        with tempfile.TemporaryDirectory(prefix="ianuacare-whisper-") as tmp_dir:
            for chunk_start, chunk_end in chunk_ranges:
                chunk = y[chunk_start:chunk_end]
                t0 = float(chunk_start) / float(sr)
                tmp_path = os.path.join(tmp_dir, f"chunk_{chunk_start}_{chunk_end}.wav")
                sf.write(tmp_path, chunk, int(sr), subtype="PCM_16")
                with open(tmp_path, "rb") as f:
                    part = self._transcribe_file_handle(
                        f, language=language, response_format=response_format
                    )
                text_parts.append(part.text)
                for seg in part.segments:
                    all_segments.append(
                        WhisperSegment(
                            start=t0 + seg.start,
                            end=t0 + seg.end,
                            text=seg.text,
                        )
                    )

        merged_text = " ".join(t for t in text_parts if t.strip()).strip()
        return WhisperResult(text=merged_text, segments=all_segments)

    def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
        response_format: str = "verbose_json",
    ) -> WhisperResult:
        if self._client is None:
            return WhisperResult(text="", segments=[])

        try:
            size = os.path.getsize(audio_path)
        except OSError:
            size = _MAX_UPLOAD_BYTES + 1

        if size <= _MAX_UPLOAD_BYTES:
            with open(audio_path, "rb") as f:
                return self._transcribe_file_handle(
                    f, language=language, response_format=response_format
                )

        return self._transcribe_chunked(
            audio_path, language=language, response_format=response_format
        )


# Backward-compatible name used across products and docs.
WhisperTranscriber = OpenAISpeechTranscriber
