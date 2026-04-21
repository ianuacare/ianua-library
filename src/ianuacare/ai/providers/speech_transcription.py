"""Speech transcription provider returning raw backend payloads."""

from __future__ import annotations

import os
import tempfile
from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.providers.base import AIProvider

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SAFE_CHUNK_BYTES = 24 * 1024 * 1024
_WAV_HEADER_MARGIN = 4096


class SpeechTranscriptionProvider(AIProvider):
    """Adapter for file-based ASR providers (for example OpenAI audio API)."""

    def __init__(
        self,
        client: Any | None = None,
        model: str = "whisper-1",
        *,
        provider: str = "openai",
        api_key: str | None = None,
    ) -> None:
        self._client = client if client is not None else self._build_client(provider, api_key)
        self._model = model

    @staticmethod
    def _build_client(provider: str, api_key: str | None) -> Any | None:
        selected = str(provider or "").strip().lower() or "openai"
        if selected != "openai":
            return None
        if not isinstance(api_key, str) or not api_key.strip():
            return None

        try:
            from openai import OpenAI
        except Exception:
            return None

        try:
            return OpenAI(api_key=api_key.strip())
        except Exception:
            return None

    @staticmethod
    def _max_samples_per_wav_chunk() -> int:
        byte_budget = _SAFE_CHUNK_BYTES - _WAV_HEADER_MARGIN
        return max(1000, byte_budget // 2)

    def infer(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> dict[str, Any]:
        _ = model_type
        if self._client is None:
            return {"text": "", "segments": []}
        if not isinstance(payload, dict):
            raise ValueError("speech transcription payload must be a mapping")

        audio_path = payload.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path:
            raise ValueError("payload.audio_path is required")
        if not os.path.isfile(audio_path) or not os.access(audio_path, os.R_OK):
            raise ValueError(f"audio file not found or not readable: {audio_path!r}")

        language = payload.get("language")
        response_format = str(payload.get("response_format") or "verbose_json")
        selected_model = model_name or self._model

        try:
            size = os.path.getsize(audio_path)
        except OSError as exc:
            raise ValueError(f"cannot read audio file size: {audio_path!r}") from exc

        if size <= _MAX_UPLOAD_BYTES:
            with open(audio_path, "rb") as f:
                return self._transcribe_file_handle(
                    selected_model,
                    f,
                    language=language if isinstance(language, str) else None,
                    response_format=response_format,
                )

        return self._transcribe_chunked(
            selected_model,
            audio_path,
            language=language if isinstance(language, str) else None,
            response_format=response_format,
        )

    def _transcribe_file_handle(
        self,
        model_name: str,
        file_handle: Any,
        *,
        language: str | None,
        response_format: str,
    ) -> dict[str, Any]:
        assert self._client is not None
        resp = self._client.audio.transcriptions.create(
            model=model_name,
            file=file_handle,
            language=language,
            response_format=response_format,
        )
        raw_segments = getattr(resp, "segments", None) or []
        segments = []
        for seg in raw_segments:
            start = to_float(getattr(seg, "start", 0.0), 0.0)
            end = to_float(getattr(seg, "end", None), start)
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": str(getattr(seg, "text", "")).strip(),
                }
            )
        return {
            "text": str(getattr(resp, "text", "")).strip(),
            "segments": segments,
        }

    def _transcribe_chunked(
        self,
        model_name: str,
        audio_path: str,
        *,
        language: str | None,
        response_format: str,
    ) -> dict[str, Any]:
        import librosa
        import soundfile as sf

        assert self._client is not None
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        total = int(len(y))
        if total == 0:
            return {"text": "", "segments": []}

        max_samples = self._max_samples_per_wav_chunk()
        text_parts: list[str] = []
        merged_segments: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="ianuacare-whisper-") as tmp_dir:
            start = 0
            while start < total:
                end = min(start + max_samples, total)
                chunk = y[start:end]
                chunk_offset_seconds = float(start) / float(sr)
                tmp_path = os.path.join(tmp_dir, f"chunk_{start}_{end}.wav")
                sf.write(tmp_path, chunk, int(sr), subtype="PCM_16")
                with open(tmp_path, "rb") as f:
                    part = self._transcribe_file_handle(
                        model_name,
                        f,
                        language=language,
                        response_format=response_format,
                    )
                text_parts.append(str(part.get("text", "")).strip())
                for segment in part.get("segments", []):
                    if not isinstance(segment, dict):
                        continue
                    seg_start = to_float(segment.get("start"), 0.0)
                    seg_end = to_float(segment.get("end"), seg_start)
                    merged_segments.append(
                        {
                            "start": chunk_offset_seconds + seg_start,
                            "end": chunk_offset_seconds + seg_end,
                            "text": str(segment.get("text", "")).strip(),
                        }
                    )
                start = end

        return {
            "text": " ".join(piece for piece in text_parts if piece).strip(),
            "segments": merged_segments,
        }
