"""Speaker embedding model using pyannote/embedding."""

from __future__ import annotations

import os
from importlib import import_module
from math import sqrt
from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

_DEFAULT_MODEL_ID = "pyannote/embedding"
_MIN_SEGMENT_SECONDS = 0.05
_TARGET_SAMPLE_RATE = 16_000


def _is_gated_repo_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"GatedRepoError", "HTTPError"}:
        return True
    message = str(exc).lower()
    return "gated" in message or "403" in message or "not in the authorized list" in message


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = sqrt(sum(component * component for component in vector))
    if norm <= 0.0:
        return list(vector)
    return [component / norm for component in vector]


def _numpy_embedding_to_list(embedding: Any) -> list[float]:
    data = getattr(embedding, "data", embedding)
    if hasattr(data, "tolist"):
        flat = data.tolist()
    elif hasattr(data, "reshape"):
        flat = data.reshape(-1).tolist()
    else:
        flat = list(data)
    if flat and isinstance(flat[0], list):
        flat = flat[0]
    return [float(value) for value in flat]


class SpeakerEmbedder(BaseAIModel):
    """Extract L2-normalized speaker embeddings from audio segments via pyannote."""

    def __init__(
        self,
        *,
        model_id: str = _DEFAULT_MODEL_ID,
        hf_token: str | None = None,
        device: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._hf_token = hf_token
        self._device = device
        self._inference: Any | None = None
        self._audio_cache: dict[str, dict[str, Any]] = {}

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

    def _ensure_inference(self) -> Any:
        if self._inference is not None:
            return self._inference

        try:
            model_mod = import_module("pyannote.audio")
            torch_mod = import_module("torch")
        except ImportError as exc:
            raise InferenceError(
                "pyannote.audio and torch are required for SpeakerEmbedder; "
                'install with pip install -e ".[audio]"'
            ) from exc

        token = self._resolve_hf_token()
        if not token:
            raise InferenceError(
                "Hugging Face token is required for pyannote/embedding; "
                "set HF_TOKEN or HUGGINGFACE_TOKEN, or pass hf_token to SpeakerEmbedder()"
            )

        model_cls = model_mod.Model
        inference_cls = model_mod.Inference

        try:
            model = model_cls.from_pretrained(self._model_id, token=token)
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", None) or str(exc)
            raise InferenceError(
                f"failed to load speaker embedding model {self._model_id}: "
                f"missing dependency {missing!r}; "
                'reinstall with pip install -e ".[audio]"'
            ) from exc
        except Exception as exc:
            if _is_gated_repo_error(exc):
                raise InferenceError(
                    "Cannot download pyannote/embedding: access not granted. "
                    "Log in on Hugging Face, open https://huggingface.co/pyannote/embedding, "
                    "accept the user conditions, then use an HF token from the same account "
                    "with read access (HF_TOKEN or HUGGINGFACE_TOKEN)."
                ) from exc
            raise InferenceError(
                f"failed to load speaker embedding model {self._model_id}"
            ) from exc
        inference = inference_cls(model, window="whole")
        device_name = self._device or ("cuda" if torch_mod.cuda.is_available() else "cpu")
        inference.to(torch_mod.device(device_name))
        self._inference = inference
        return inference

    def _resolve_hf_token(self) -> str | None:
        if isinstance(self._hf_token, str) and self._hf_token.strip():
            return self._hf_token.strip()
        env_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        if isinstance(env_token, str) and env_token.strip():
            return env_token.strip()
        return None

    def _load_audio_file(self, audio_path: str) -> dict[str, Any]:
        cached = self._audio_cache.get(audio_path)
        if cached is not None:
            return cached

        try:
            librosa = import_module("librosa")
            torch_mod = import_module("torch")
        except ImportError as exc:
            raise InferenceError(
                "librosa and torch are required to load audio for speaker embedding"
            ) from exc

        try:
            waveform_np, sample_rate = librosa.load(
                audio_path,
                sr=_TARGET_SAMPLE_RATE,
                mono=True,
            )
        except Exception as exc:
            raise InferenceError(f"failed to load audio file: {audio_path}") from exc

        waveform = torch_mod.from_numpy(waveform_np).unsqueeze(0).float()
        loaded = {"waveform": waveform, "sample_rate": int(sample_rate)}
        self._audio_cache[audio_path] = loaded
        return loaded

    def _embed_segments(self, audio_path: str, segments: list[Any]) -> list[list[float]]:
        if not segments:
            return []

        inference = self._ensure_inference()
        segment_mod = import_module("pyannote.core")
        segment_cls = segment_mod.Segment
        audio_file = self._load_audio_file(audio_path)

        vectors: list[list[float]] = []
        for index, item in enumerate(segments):
            if not isinstance(item, dict):
                raise ValidationError(f"segments[{index}] must be a mapping")
            start = to_float(item.get("start"), 0.0)
            end = to_float(item.get("end"), start)
            vectors.append(
                self._embed_excerpt_with_inference(
                    inference,
                    segment_cls,
                    audio_file,
                    start,
                    end,
                )
            )
        return vectors

    def _embed_excerpt(self, audio_path: str, start: float, end: float) -> list[float]:
        inference = self._ensure_inference()
        segment_mod = import_module("pyannote.core")
        segment_cls = segment_mod.Segment
        audio_file = self._load_audio_file(audio_path)
        return self._embed_excerpt_with_inference(
            inference,
            segment_cls,
            audio_file,
            start,
            end,
        )

    @staticmethod
    def _embed_excerpt_with_inference(
        inference: Any,
        segment_cls: Any,
        audio_file: dict[str, Any],
        start: float,
        end: float,
    ) -> list[float]:
        duration = max(0.0, end - start)
        if duration < _MIN_SEGMENT_SECONDS:
            return []

        excerpt = segment_cls(start, end)
        try:
            embedding = inference.crop(audio_file, excerpt)
        except Exception as exc:
            raise InferenceError(
                f"failed to extract speaker embedding for [{start:.3f}, {end:.3f}]"
            ) from exc

        vector = _numpy_embedding_to_list(embedding)
        if not vector:
            return []
        return _l2_normalize(vector)
