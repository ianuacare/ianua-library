"""Model output normalizer for provider-agnostic model runs."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float


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
