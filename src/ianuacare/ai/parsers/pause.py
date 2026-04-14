"""Pause-aware transcript parser."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.parsers.base import BaseParser

_DEFAULT_GAP_SECONDS = 1.5


class PauseParser(BaseParser):
    """Merge consecutive segments if the gap between them is at most ``silence_gap_seconds``."""

    def __init__(self, silence_gap_seconds: float = _DEFAULT_GAP_SECONDS) -> None:
        self._gap = silence_gap_seconds

    def parse(self, data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            start = to_float(item.get("start"), 0.0)
            end_raw = item.get("end")
            end = to_float(end_raw if end_raw is not None else item.get("start"), start)
            normalized.append({"start": start, "end": end, "text": text})

        if not normalized:
            return []

        normalized.sort(key=lambda s: to_float(s.get("start"), 0.0))

        merged: list[dict[str, Any]] = []
        current = dict(normalized[0])
        for nxt in normalized[1:]:
            gap = to_float(nxt.get("start"), 0.0) - to_float(current.get("end"), 0.0)
            if gap <= self._gap:
                current["end"] = max(
                    to_float(current.get("end"), 0.0),
                    to_float(nxt.get("end"), 0.0),
                )
                current["text"] = " ".join(
                    t for t in (current["text"], nxt["text"]) if t
                ).strip()
            else:
                merged.append(current)
                current = dict(nxt)
        merged.append(current)
        return merged
