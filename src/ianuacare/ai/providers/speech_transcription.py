"""Speech transcription provider returning raw backend payloads."""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from importlib import import_module
from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.providers.base import AIProvider

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SAFE_CHUNK_BYTES = 24 * 1024 * 1024
_WAV_HEADER_MARGIN = 4096
# Frames read from the source per I/O call while streaming a chunk to disk.
# Bounds memory independently of file length, sample rate and channel count.
_READ_BLOCK_FRAMES = 1 << 18
# Hard cap on chunk duration, on top of the byte budget: low sample rates (8 kHz)
# would otherwise yield chunks longer than OpenAI-compatible ASR models accept.
_MAX_CHUNK_SECONDS = 1200
# Containers streamed directly with libsndfile: PCM/lossless, decoded frame-exactly.
# Everything else (MP3, OGG, M4A...) is transcoded by ffmpeg first, because
# libsndfile may open a lossy header and then fail mid-decode after some chunks
# were already sent (and billed).
_STREAMABLE_FORMATS = frozenset({"WAV", "WAVEX", "FLAC", "AIFF"})
# Format produced when ffmpeg normalizes the other inputs.
_FFMPEG_SAMPLE_RATE = 16_000
_DEFAULT_FFMPEG_TIMEOUT_SECONDS = 900.0

_LOG = logging.getLogger(__name__)

# Yields (chunk_wav_path, offset_seconds); a Generator so callers can close() it.
_ChunkStream = Generator[tuple[str, float], None, None]

# Providers that speak the OpenAI Chat/Audio wire format and can be reached
# with the official `openai` Python SDK by overriding `base_url`.
_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "groq"}
_DEFAULT_PROVIDER_BASE_URLS = {"groq": "https://api.groq.com/openai/v1"}


class SpeechTranscriptionProvider(AIProvider):
    """Adapter for file-based ASR providers (for example OpenAI audio API)."""

    def __init__(
        self,
        client: Any | None = None,
        model: str = "whisper-1",
        *,
        provider: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        ffmpeg_timeout_seconds: float = _DEFAULT_FFMPEG_TIMEOUT_SECONDS,
    ) -> None:
        self._client = (
            client if client is not None else self._build_client(provider, api_key, base_url)
        )
        self._model = model
        self._temperature = temperature
        self._ffmpeg_timeout_seconds = ffmpeg_timeout_seconds

    @staticmethod
    def _build_client(
        provider: str, api_key: str | None, base_url: str | None = None
    ) -> Any | None:
        selected = str(provider or "").strip().lower() or "openai"
        if selected not in _OPENAI_COMPATIBLE_PROVIDERS:
            return None
        if not isinstance(api_key, str) or not api_key.strip():
            return None

        try:
            from openai import OpenAI
        except Exception:
            return None

        resolved_base_url = (base_url or "").strip() or _DEFAULT_PROVIDER_BASE_URLS.get(selected)
        client_kwargs: dict[str, Any] = {"api_key": api_key.strip()}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url

        try:
            return OpenAI(**client_kwargs)
        except Exception:
            return None

    @staticmethod
    def _max_samples_per_wav_chunk(sample_rate: int | None = None) -> int:
        """Frames per chunk WAV. Chunks are always mono PCM_16 (2 bytes per frame),
        so the byte budget ignores the source channel count; with ``sample_rate``
        the chunk is also capped at ``_MAX_CHUNK_SECONDS``."""
        byte_budget = _SAFE_CHUNK_BYTES - _WAV_HEADER_MARGIN
        frames = max(1000, byte_budget // 2)
        if sample_rate:
            frames = min(frames, max(1, int(sample_rate * _MAX_CHUNK_SECONDS)))
        return frames

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = (model_type, params)
        if self._client is None:
            return {"text": "", "segments": [], "words": []}
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
        granularities = self._resolve_timestamp_granularities(payload)
        temperature = self._resolve_temperature(payload)

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
                    timestamp_granularities=granularities,
                    temperature=temperature,
                )

        return self._transcribe_chunked(
            selected_model,
            audio_path,
            language=language if isinstance(language, str) else None,
            response_format=response_format,
            timestamp_granularities=granularities,
            temperature=temperature,
        )

    def _resolve_timestamp_granularities(self, payload: dict[str, Any]) -> list[str] | None:
        """Explicit ``timestamp_granularities`` wins; else fall back to the
        legacy ``word_timestamps`` boolean (kept for backward compatibility)."""
        explicit = payload.get("timestamp_granularities")
        if explicit is not None:
            granularities = [str(g).strip() for g in explicit if str(g).strip()]
            return granularities or None
        if bool(payload.get("word_timestamps", False)):
            return ["word", "segment"]
        return None

    def _resolve_temperature(self, payload: dict[str, Any]) -> float | None:
        explicit = payload.get("temperature")
        if explicit is not None:
            try:
                return float(explicit)
            except (TypeError, ValueError):
                return None
        return self._temperature

    def _transcribe_file_handle(
        self,
        model_name: str,
        file_handle: Any,
        *,
        language: str | None,
        response_format: str,
        timestamp_granularities: list[str] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        assert self._client is not None
        kwargs: dict[str, Any] = {
            "model": model_name,
            "file": file_handle,
            "language": language,
            "response_format": response_format,
        }
        if timestamp_granularities:
            kwargs["timestamp_granularities"] = timestamp_granularities
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.audio.transcriptions.create(**kwargs)
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
        words: list[dict[str, Any]] = []
        if timestamp_granularities and "word" in timestamp_granularities:
            raw_words = getattr(resp, "words", None) or []
            for w in raw_words:
                w_start = to_float(getattr(w, "start", 0.0), 0.0)
                w_end = to_float(getattr(w, "end", None), w_start)
                words.append(
                    {
                        "start": w_start,
                        "end": w_end,
                        "text": str(getattr(w, "word", "")).strip(),
                    }
                )
        return {
            "text": str(getattr(resp, "text", "")).strip(),
            "segments": segments,
            "words": words,
        }

    def _transcribe_chunked(
        self,
        model_name: str,
        audio_path: str,
        *,
        language: str | None,
        response_format: str,
        timestamp_granularities: list[str] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        assert self._client is not None
        text_parts: list[str] = []
        merged_segments: list[dict[str, Any]] = []
        merged_words: list[dict[str, Any]] = []
        chunk_count = 0

        with (
            tempfile.TemporaryDirectory(prefix="ianuacare-whisper-") as tmp_dir,
            # Close the generator (and the source SoundFile it holds) before the
            # temp dir is removed, also when an API call fails mid-way.
            contextlib.closing(self._iter_wav_chunks(audio_path, tmp_dir)) as chunks,
        ):
            for chunk_path, chunk_offset_seconds in chunks:
                chunk_count += 1
                with open(chunk_path, "rb") as f:
                    part = self._transcribe_file_handle(
                        model_name,
                        f,
                        language=language,
                        response_format=response_format,
                        timestamp_granularities=timestamp_granularities,
                        temperature=temperature,
                    )
                os.remove(chunk_path)
                text_parts.append(str(part.get("text", "")).strip())
                merged_segments.extend(_shift_items(part.get("segments", []), chunk_offset_seconds))
                merged_words.extend(_shift_items(part.get("words", []), chunk_offset_seconds))

        if chunk_count == 0:
            return {"text": "", "segments": []}
        return {
            "text": " ".join(piece for piece in text_parts if piece).strip(),
            "segments": merged_segments,
            "words": merged_words,
        }

    def _iter_wav_chunks(self, audio_path: str, tmp_dir: str) -> _ChunkStream:
        """Yield ``(chunk_wav_path, offset_seconds)`` without decoding the whole file.

        PCM/lossless containers (``_STREAMABLE_FORMATS``) are streamed with
        libsndfile; anything else is transcoded by ffmpeg to 16 kHz mono PCM WAV
        and that is streamed; without ffmpeg, fall back to a full in-memory
        decode with librosa.
        """
        if _soundfile_format(audio_path) in _STREAMABLE_FORMATS:
            yield from self._iter_wav_chunks_streaming(audio_path, tmp_dir)
            return
        converted = _convert_with_ffmpeg(audio_path, tmp_dir, self._ffmpeg_timeout_seconds)
        if converted is None:
            _LOG.warning(
                "speech_transcription: %s is not a PCM/lossless format and ffmpeg is "
                "unavailable; decoding the whole file in memory (high RAM usage)",
                os.path.basename(audio_path),
            )
            yield from self._iter_wav_chunks_in_memory(audio_path, tmp_dir)
            return
        yield from self._iter_wav_chunks_streaming(converted, tmp_dir)

    def _iter_wav_chunks_streaming(
        self, audio_path: str, tmp_dir: str
    ) -> _ChunkStream:
        sf = import_module("soundfile")
        with sf.SoundFile(audio_path) as source:
            sr = int(source.samplerate)
            max_frames = self._max_samples_per_wav_chunk(sr)
            start = 0
            while True:
                chunk_path = os.path.join(tmp_dir, f"chunk_{start}.wav")
                written = 0
                with sf.SoundFile(
                    chunk_path, mode="w", samplerate=sr, channels=1, subtype="PCM_16"
                ) as sink:
                    while written < max_frames:
                        to_read = min(_READ_BLOCK_FRAMES, max_frames - written)
                        block = source.read(to_read, dtype="float32", always_2d=True)
                        if len(block) == 0:
                            break
                        sink.write(block.mean(axis=1))
                        written += len(block)
                if written == 0:
                    os.remove(chunk_path)
                    return
                yield chunk_path, float(start) / float(sr)
                start += written

    def _iter_wav_chunks_in_memory(
        self, audio_path: str, tmp_dir: str
    ) -> _ChunkStream:
        librosa = import_module("librosa")
        sf = import_module("soundfile")
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        total = int(len(y))
        max_samples = self._max_samples_per_wav_chunk(int(sr))
        start = 0
        while start < total:
            end = min(start + max_samples, total)
            chunk_path = os.path.join(tmp_dir, f"chunk_{start}_{end}.wav")
            sf.write(chunk_path, y[start:end], int(sr), subtype="PCM_16")
            yield chunk_path, float(start) / float(sr)
            start = end


def _shift_items(items: Any, offset_seconds: float) -> list[dict[str, Any]]:
    """Shift ``start``/``end`` of chunk-local segments or words by the chunk offset."""
    shifted: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_start = to_float(item.get("start"), 0.0)
        item_end = to_float(item.get("end"), item_start)
        shifted.append(
            {
                "start": offset_seconds + item_start,
                "end": offset_seconds + item_end,
                "text": str(item.get("text", "")).strip(),
            }
        )
    return shifted


def _soundfile_format(audio_path: str) -> str | None:
    """libsndfile container name (``WAV``, ``FLAC``, ``MP3``...) or ``None``."""
    sf = import_module("soundfile")
    try:
        return str(sf.info(audio_path).format)
    except Exception:
        return None


def _convert_with_ffmpeg(audio_path: str, tmp_dir: str, timeout_seconds: float) -> str | None:
    """Transcode to 16 kHz mono PCM_16 WAV on disk; ``None`` if ffmpeg is missing.

    ffmpeg streams internally, so memory stays flat regardless of input length.
    Raises ``ValueError`` if ffmpeg is present but cannot decode the input or
    exceeds ``timeout_seconds``; a partial output file is removed.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    target = os.path.join(tmp_dir, "source_16k_mono.wav")
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        audio_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(_FFMPEG_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        target,
    ]
    name = os.path.basename(audio_path)
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _remove_quietly(target)
        raise ValueError(
            f"ffmpeg timed out after {timeout_seconds:g}s converting audio file {name!r}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        _remove_quietly(target)
        detail = (exc.stderr or b"").decode("utf-8", errors="replace").strip()[-500:]
        raise ValueError(f"ffmpeg could not decode audio file {name!r}: {detail}") from exc
    return target


def _remove_quietly(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
