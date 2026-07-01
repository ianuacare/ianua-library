"""CAM++ speaker embedding model served in-process via ONNX Runtime.

Drop-in replacement for :class:`SpeakerEmbedder` (MFCC): same
``run(payload) -> list[float] | list[list[float]]`` contract, so
``DiarizationModel`` and ``SpeakerClusterer`` are unchanged.

CAM++ produces 192-dim speaker embeddings that discriminate voices far better
than MFCC statistics. Inference is in-process (no model server) and torch-free:
``onnxruntime`` runs the exported CAM++ graph, ``kaldi-native-fbank`` computes
the 80-dim Kaldi fbank the model was trained on (using librosa/torchaudio-kaldi
features would drift from training and degrade embeddings).
"""

from __future__ import annotations

import os
from importlib import import_module
from math import sqrt
from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

_TARGET_SAMPLE_RATE = 16_000
_NUM_MEL_BINS = 80
# CAM++ needs enough speech to form a stable embedding; below this the vector is
# noise and hurts clustering. Short segments return [] (clusterer maps to spk 0).
# Merging of micro-turns before embedding is handled upstream (segment_duration).
_MIN_SEGMENT_SECONDS = 0.5
_MODEL_PATH_ENV = "CAMPP_ONNX_PATH"


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = sqrt(sum(component * component for component in vector))
    if norm <= 0.0:
        return list(vector)
    return [component / norm for component in vector]


class CamPlusPlusEmbedder(BaseAIModel):
    """Extract L2-normalized CAM++ speaker embeddings from audio segments."""

    def __init__(
        self,
        *,
        model_path: str | None = None,
        sample_rate: int = _TARGET_SAMPLE_RATE,
        num_mel_bins: int = _NUM_MEL_BINS,
        min_segment_seconds: float = _MIN_SEGMENT_SECONDS,
    ) -> None:
        self._model_path = model_path or os.environ.get(_MODEL_PATH_ENV, "")
        self._sample_rate = sample_rate
        self._num_mel_bins = num_mel_bins
        self._min_segment_seconds = max(0.0, min_segment_seconds)
        self._waveform_cache: dict[str, tuple[Any, int]] = {}
        self._session: Any = None
        self._input_name: str | None = None

    # ------------------------------------------------------------------ contract
    def run(self, payload: Any) -> list[float] | list[list[float]]:
        if not isinstance(payload, dict):
            raise ValidationError("campp embedder payload must be a mapping")

        audio_path = payload.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            raise ValidationError("audio_path is required for speaker embedding")

        segments = payload.get("segments")
        if isinstance(segments, list):
            return self._embed_segments(audio_path.strip(), segments)

        start = to_float(payload.get("start"), 0.0)
        end = to_float(payload.get("end"), start)
        return self._embed_excerpt(audio_path.strip(), start, end)

    # ------------------------------------------------------------------- session
    def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session

        if not self._model_path or not os.path.isfile(self._model_path):
            raise InferenceError(
                "CAM++ ONNX model not found; set the "
                f"{_MODEL_PATH_ENV} env var (or model_path=) to the .onnx file"
            )
        try:
            ort = import_module("onnxruntime")
        except ImportError as exc:
            raise InferenceError(
                "onnxruntime is required for CamPlusPlusEmbedder; "
                'install with pip install -e ".[audio]"'
            ) from exc

        try:
            session = ort.InferenceSession(
                self._model_path, providers=["CPUExecutionProvider"]
            )
        except Exception as exc:
            raise InferenceError(
                f"failed to load CAM++ ONNX model: {self._model_path}"
            ) from exc

        self._session = session
        self._input_name = session.get_inputs()[0].name
        return session

    # ----------------------------------------------------------------- waveforms
    def _load_waveform(self, audio_path: str) -> tuple[Any, int]:
        cached = self._waveform_cache.get(audio_path)
        if cached is not None:
            return cached
        try:
            librosa = import_module("librosa")
        except ImportError as exc:
            raise InferenceError(
                "librosa is required for CamPlusPlusEmbedder; "
                'install with pip install -e ".[audio]"'
            ) from exc
        try:
            y, sr = librosa.load(audio_path, sr=self._sample_rate, mono=True)
        except Exception as exc:
            raise InferenceError(f"failed to load audio file: {audio_path}") from exc
        loaded = (y, int(sr))
        self._waveform_cache[audio_path] = loaded
        return loaded

    # ------------------------------------------------------------------ features
    def _fbank(self, excerpt: Any, sr: int) -> Any:
        """80-dim Kaldi fbank with per-utterance mean normalization (CMN).

        Matches 3D-Speaker/WeSpeaker CAM++ training features: 25ms window, 10ms
        shift, no dither, then subtract the time-mean (as CAM++ does before the
        network).
        """
        knf = import_module("kaldi_native_fbank")
        np = import_module("numpy")

        opts = knf.FbankOptions()
        opts.frame_opts.samp_freq = float(sr)
        opts.frame_opts.dither = 0.0
        opts.frame_opts.snip_edges = False
        opts.mel_opts.num_bins = self._num_mel_bins

        fbank = knf.OnlineFbank(opts)
        # kaldi-native-fbank expects samples in int16 amplitude range.
        samples = (np.asarray(excerpt, dtype=np.float32) * 32768.0).tolist()
        fbank.accept_waveform(float(sr), samples)
        fbank.input_finished()

        frames = [fbank.get_frame(i) for i in range(fbank.num_frames_ready)]
        if not frames:
            return None
        feats = np.asarray(frames, dtype=np.float32)
        feats = feats - feats.mean(axis=0, keepdims=True)
        return feats

    # -------------------------------------------------------------------- embeds
    def _embed_segments(self, audio_path: str, segments: list[Any]) -> list[list[float]]:
        if not segments:
            return []
        self._ensure_session()  # fail fast if model/onnxruntime missing
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
        self._ensure_session()  # fail fast if model/onnxruntime missing
        y, sr = self._load_waveform(audio_path)
        return self._embed_excerpt_waveform(y, sr, start, end)

    def _embed_excerpt_waveform(self, y: Any, sr: int, start: float, end: float) -> list[float]:
        if max(0.0, end - start) < self._min_segment_seconds:
            return []
        start_sample = max(0, int(start * sr))
        end_sample = min(len(y), int(end * sr))
        if end_sample <= start_sample:
            return []

        np = import_module("numpy")
        excerpt = y[start_sample:end_sample]
        feats = self._fbank(excerpt, sr)
        if feats is None or feats.shape[0] == 0:
            return []

        session = self._ensure_session()
        model_input = np.expand_dims(feats, axis=0).astype(np.float32)  # [1, T, 80]
        try:
            outputs = session.run(None, {self._input_name: model_input})
        except Exception as exc:
            raise InferenceError(
                f"CAM++ inference failed for [{start:.3f}, {end:.3f}]"
            ) from exc

        embedding = np.asarray(outputs[0]).reshape(-1).astype(float)
        if embedding.size == 0:
            return []
        return _l2_normalize([float(v) for v in embedding.tolist()])
