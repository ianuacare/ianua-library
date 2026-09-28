"""Dimensional speech emotion model (arousal, dominance, valence)."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.parsers.audio_clips import iter_segment_clips, positive_seconds, segment_bounds
from ianuacare.ai.providers.base import AIProvider
from ianuacare.core.exceptions.errors import ValidationError


class AudioEmotionModel(NLPModel):
    """Inference model for audio emotion recognition via a REST-hosted provider."""

    def __init__(
        self,
        provider: AIProvider,
        model_name: str,
        normalizer: ModelOutNormalizer,
        *,
        min_clip_seconds: float = 1.0,
        max_clip_seconds: float = 300.0,
        merge_consecutive: bool = False,
    ) -> None:
        super().__init__(provider, model_name)
        self._normalizer = normalizer
        self._defaults = {
            "min_clip_seconds": min_clip_seconds,
            "max_clip_seconds": max_clip_seconds,
            "merge_consecutive": merge_consecutive,
        }
        self._options(self._defaults)

    @staticmethod
    def _options(options: dict[str, Any]) -> tuple[float, float, bool]:
        minimum = positive_seconds(options["min_clip_seconds"], "min_clip_seconds")
        maximum = positive_seconds(options["max_clip_seconds"], "max_clip_seconds")
        merge = options["merge_consecutive"]
        if not 0.1 <= minimum <= maximum <= 300:
            raise ValidationError("require 0.1 <= min_clip_seconds <= max_clip_seconds <= 300")
        if not isinstance(merge, bool):
            raise ValidationError("merge_consecutive must be a boolean")
        return minimum, maximum, merge

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict) or "segments" not in payload:
            raw = self._provider.infer(self._model_name, payload)
            return self._normalizer.normalize_audio_emotion(raw)
        if payload.get("speaker_id") is None:
            raise ValidationError("speaker_id is required when segments are present")
        segments = payload["segments"]
        if not isinstance(segments, list):
            raise ValidationError("segments must be a list")
        minimum, maximum, merge = self._options({**self._defaults, **payload})
        selected: list[dict[str, Any]] = []
        previous_selected = False
        last_end = 0.0
        for segment in segments:
            start, end = segment_bounds(segment)
            if start < last_end:
                raise ValidationError("segments must be ordered and non-overlapping")
            last_end = end
            matches = segment.get("speaker_id") == payload["speaker_id"]
            if matches:
                # Only touching runs are merged: never include silence or another speaker.
                if merge and previous_selected and selected[-1]["end"] == start:
                    selected[-1]["end"] = end
                else:
                    selected.append({"start": start, "end": end})
            previous_selected = matches
        if not selected:
            raise ValidationError("No segments survive the speaker filter")
        audio = payload.get("audio_bytes")
        if audio is None:
            audio = payload.get("audio_path")
        if audio is None:
            raise ValidationError("audio_path or audio_bytes is required for batch emotion")
        skipped: list[dict[str, Any]] = []
        per_segment: list[dict[str, Any]] = []
        for clip in iter_segment_clips(audio, selected, max_clip_seconds=maximum):
            metadata = {k: clip[k] for k in ("start", "end", "duration")}
            if clip["duration"] < minimum:
                skipped.append({**metadata, "reason": "below_min_clip_seconds"})
                continue
            raw = self._provider.infer(self._model_name, {"audio_bytes": clip["audio_bytes"]})
            per_segment.append(
                {**metadata, "scores": self._normalizer.normalize_audio_emotion(raw)}
            )
        if not per_segment:
            raise ValidationError("No segments survive min_clip_seconds")
        duration = sum(item["duration"] for item in per_segment)
        mean = {
            key: sum(item["scores"][key] * item["duration"] for item in per_segment) / duration
            for key in ("arousal", "dominance", "valence")
        }
        return {
            **mean,
            "mean": mean,
            "per_segment": per_segment,
            "speaker_id": payload["speaker_id"],
            "segment_count": len(per_segment),
            "skipped": skipped,
        }
