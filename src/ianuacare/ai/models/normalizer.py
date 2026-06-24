"""Model output normalizer for provider-agnostic model runs."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.core.exceptions.errors import InferenceError


class ModelOutNormalizer:
    """Single concrete normalizer used by all AI models."""

    def normalize_transcript(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, str):
            return {"text": raw.strip(), "segments": []}
        if not isinstance(raw, dict):
            return {"text": str(raw), "segments": []}

        text = str(raw.get("text") or "").strip()
        segments_raw = raw.get("segments")
        if not isinstance(segments_raw, list):
            return {"text": text, "segments": []}

        segments: list[dict[str, Any]] = []
        for segment in segments_raw:
            if not isinstance(segment, dict):
                continue
            start = to_float(segment.get("start"), 0.0)
            end_raw = segment.get("end")
            end = to_float(end_raw if end_raw is not None else segment.get("start"), start)
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": str(segment.get("text", "")).strip(),
                }
            )
        return {"text": text, "segments": segments}

    def normalize_summary(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, str):
            points = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
            return {"text": raw.strip(), "key_points": points[:6]}

        if isinstance(raw, dict):
            text = str(raw.get("text") or raw.get("summary") or "").strip()
            points_raw = raw.get("key_points")
            if isinstance(points_raw, list):
                key_points = [str(point).strip() for point in points_raw if str(point).strip()]
            else:
                key_points = [
                    line.strip("- ").strip() for line in text.splitlines() if line.strip()
                ]
            return {"text": text, "key_points": key_points[:6]}

        text = str(raw).strip()
        return {"text": text, "key_points": [text] if text else []}

    def normalize_task(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        return {"result": raw}

    def normalize_audio_emotion(self, raw: Any) -> dict[str, float]:
        """Normalize arousal, dominance, and valence from provider output."""
        adv = self._coerce_adv(raw)
        if adv is None:
            raise InferenceError("audio emotion response format is not recognized")
        return adv

    @staticmethod
    def _coerce_adv(raw: Any) -> dict[str, float] | None:
        if isinstance(raw, dict):
            arousal = raw.get("arousal")
            dominance = raw.get("dominance")
            valence = raw.get("valence")
            if arousal is not None and dominance is not None and valence is not None:
                return {
                    "arousal": to_float(arousal, 0.0),
                    "dominance": to_float(dominance, 0.0),
                    "valence": to_float(valence, 0.0),
                }
            return None

        values: list[Any] | None = None
        if isinstance(raw, list):
            if raw and isinstance(raw[0], list):
                row = raw[0]
                if isinstance(row, list) and len(row) >= 3:
                    values = row[:3]
            elif len(raw) >= 3 and not isinstance(raw[0], dict):
                values = raw[:3]
            elif raw and all(isinstance(item, dict) for item in raw):
                by_label: dict[str, float] = {}
                for item in raw:
                    label = str(item.get("label", "")).strip().lower()
                    if not label:
                        continue
                    by_label[label] = to_float(item.get("score"), 0.0)
                arousal = by_label.get("arousal")
                dominance = by_label.get("dominance")
                valence = by_label.get("valence")
                if arousal is not None and dominance is not None and valence is not None:
                    return {
                        "arousal": arousal,
                        "dominance": dominance,
                        "valence": valence,
                    }
                return None

        if values is not None and len(values) >= 3:
            return {
                "arousal": to_float(values[0], 0.0),
                "dominance": to_float(values[1], 0.0),
                "valence": to_float(values[2], 0.0),
            }
        return None
