"""Feature extraction parser for transcript segments."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.parsers.base import BaseParser

_DEFAULT_ZERO = 0.0


class SpectralParser(BaseParser):
    """Derive lightweight deterministic features from text/timing."""

    def parse(self, data: Any) -> dict[str, float]:
        if not isinstance(data, dict):
            return {
                "duration": _DEFAULT_ZERO,
                "tokens": _DEFAULT_ZERO,
                "chars": _DEFAULT_ZERO,
                "rate": _DEFAULT_ZERO,
            }
        start = to_float(data.get("start"), _DEFAULT_ZERO)
        end = to_float(data.get("end"), start)
        text = str(data.get("text", "")).strip()
        duration = max(0.0, end - start)
        tokens = max(1, len(text.split())) if text else 0
        chars = len(text)
        rate = float(tokens) / duration if duration > 0 else float(tokens)
        return {
            "duration": duration,
            "tokens": float(tokens),
            "chars": float(chars),
            "rate": float(rate),
        }
