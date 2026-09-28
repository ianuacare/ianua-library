"""Lazy audio decoding and bounded, in-memory PCM16 WAV segment slicing."""

from __future__ import annotations

import io
import math
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ianuacare.core.exceptions.errors import InferenceError, ValidationError


def positive_seconds(value: Any, name: str) -> float:
    """Validate a finite positive duration."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a positive finite number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValidationError(f"{name} must be a positive finite number")
    return result


def segment_bounds(segment: Any) -> tuple[float, float]:
    """Validate timestamps before decoding or inference."""
    if not isinstance(segment, Mapping):
        raise ValidationError("segments must contain mappings")
    start, end = segment.get("start"), segment.get("end")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (start, end)):
        raise ValidationError("segment start and end must be finite numbers")
    assert isinstance(start, (int, float)) and isinstance(end, (int, float))
    start, end = float(start), float(end)
    if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
        raise ValidationError("segment requires 0 <= start < end and finite timestamps")
    return start, end


def iter_segment_clips(
    audio_path_or_waveform: Any,
    segments: Sequence[Mapping[str, Any]],
    *,
    sample_rate: int = 16000,
    max_clip_seconds: float = 300.0,
) -> Iterator[dict[str, Any]]:
    """Yield audio_bytes/start/end/duration; arrays are mono at ``sample_rate``.

    Paths and encoded bytes are decoded and resampled. Timestamps outside the
    recording are rejected rather than silently weighting nonexistent samples.
    """
    maximum = positive_seconds(max_clip_seconds, "max_clip_seconds")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValidationError("sample_rate must be a positive integer")
    step = int(maximum * sample_rate)
    if step < 1:
        raise ValidationError("max_clip_seconds must cover at least one sample")
    bounds = [segment_bounds(segment) for segment in segments]
    try:
        import librosa
        import numpy as np
        import soundfile as sf  # type: ignore[import-untyped]
    except ImportError as exc:
        raise InferenceError('Audio slicing requires pip install -e ".[audio]"') from exc
    source = audio_path_or_waveform
    try:
        if isinstance(source, (str, Path, bytes)):
            source = io.BytesIO(source) if isinstance(source, bytes) else str(source)
            waveform, _ = librosa.load(source, sr=sample_rate, mono=True)
        else:
            waveform = np.asarray(source, dtype=np.float32)
        if waveform.ndim != 1 or not np.isfinite(waveform).all():
            raise ValidationError("waveform must be finite mono audio")
    except ValidationError:
        raise
    except Exception as exc:
        raise InferenceError("Cannot decode audio for segment slicing") from exc
    sample_bounds = [
        (round(start * sample_rate), round(end * sample_rate)) for start, end in bounds
    ]
    if any(start >= end or end > len(waveform) for start, end in sample_bounds):
        raise ValidationError("segment is outside audio bounds or shorter than one sample")
    for start, end in sample_bounds:
        for left in range(start, end, step):
            right = min(left + step, end)
            buffer = io.BytesIO()
            sf.write(buffer, waveform[left:right], sample_rate, format="WAV", subtype="PCM_16")
            yield {
                "start": left / sample_rate,
                "end": right / sample_rate,
                "duration": (right - left) / sample_rate,
                "audio_bytes": buffer.getvalue(),
            }
