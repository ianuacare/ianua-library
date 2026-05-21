"""Speaker embedding model using librosa MFCC features."""

from __future__ import annotations

from importlib import import_module
from math import sqrt
from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

_MIN_SEGMENT_SECONDS = 0.05
_TARGET_SAMPLE_RATE = 16_000
_N_MFCC = 20


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = sqrt(sum(component * component for component in vector))
    if norm <= 0.0:
        return list(vector)
    return [component / norm for component in vector]


def _mfcc_vector(y: Any, *, sr: int, n_mfcc: int, include_delta: bool) -> list[float]:
    librosa = import_module("librosa")
    np = import_module("numpy")

    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    parts: list[Any] = [mfccs.mean(axis=1), mfccs.std(axis=1)]
    if include_delta:
        delta = librosa.feature.delta(mfccs)
        parts.extend([delta.mean(axis=1), delta.std(axis=1)])
    stacked = np.concatenate(parts)
    return [float(value) for value in stacked.tolist()]


class SpeakerEmbedder(BaseAIModel):
    """Extract L2-normalized speaker embeddings from audio segments via MFCC features."""

    def __init__(
        self,
        *,
        sample_rate: int = _TARGET_SAMPLE_RATE,
        n_mfcc: int = _N_MFCC,
        include_delta: bool = True,
    ) -> None:
        self._sample_rate = sample_rate
        self._n_mfcc = n_mfcc
        self._include_delta = include_delta
        self._waveform_cache: dict[str, tuple[Any, int]] = {}

    def run(self, payload: Any) -> list[float] | list[list[float]]:
        if not isinstance(payload, dict):
            raise ValidationError("speaker embedder payload must be a mapping")

        audio_path = payload.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise ValidationError("audio_path is required for speaker embedding")

        segments = payload.get("segments")
        if isinstance(segments, list):
            return self._embed_segments(audio_path.strip(), segments)

        start = to_float(payload.get("start"), 0.0)
        end = to_float(payload.get("end"), start)
        return self._embed_excerpt(audio_path.strip(), start, end)

    def _load_waveform(self, audio_path: str) -> tuple[Any, int]:
        cached = self._waveform_cache.get(audio_path)
        if cached is not None:
            return cached

        try:
            librosa = import_module("librosa")
        except ImportError as exc:
            raise InferenceError(
                "librosa is required for SpeakerEmbedder; "
                'install with pip install -e ".[audio]"'
            ) from exc

        try:
            y, sr = librosa.load(audio_path, sr=self._sample_rate, mono=True)
        except Exception as exc:
            raise InferenceError(f"failed to load audio file: {audio_path}") from exc

        loaded = (y, int(sr))
        self._waveform_cache[audio_path] = loaded
        return loaded

    def _embed_segments(self, audio_path: str, segments: list[Any]) -> list[list[float]]:
        if not segments:
            return []

        y, sr = self._load_waveform(audio_path)
        vectors: list[list[float]] = []
        for index, item in enumerate(segments):
            if not isinstance(item, dict):
                raise ValidationError(f"segments[{index}] must be a mapping")
            start = to_float(item.get("start"), 0.0)
            end = to_float(item.get("end"), start)
            vectors.append(self._embed_excerpt_waveform(y, sr, start, end))
        return vectors

    def _embed_excerpt(self, audio_path: str, start: float, end: float) -> list[float]:
        y, sr = self._load_waveform(audio_path)
        return self._embed_excerpt_waveform(y, sr, start, end)

    def _embed_excerpt_waveform(self, y: Any, sr: int, start: float, end: float) -> list[float]:
        duration = max(0.0, end - start)
        if duration < _MIN_SEGMENT_SECONDS:
            return []

        start_sample = max(0, int(start * sr))
        end_sample = min(len(y), int(end * sr))
        if end_sample <= start_sample:
            return []

        excerpt = y[start_sample:end_sample]
        try:
            vector = _mfcc_vector(
                excerpt,
                sr=sr,
                n_mfcc=self._n_mfcc,
                include_delta=self._include_delta,
            )
        except Exception as exc:
            raise InferenceError(
                f"failed to extract speaker embedding for [{start:.3f}, {end:.3f}]"
            ) from exc

        if not vector:
            return []
        return _l2_normalize(vector)
