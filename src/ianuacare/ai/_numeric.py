"""Shared safe numeric coercion for AI module inputs."""

from __future__ import annotations

from typing import Any


def to_float(value: Any, default: float = 0.0) -> float:
    """Parse a scalar to float; never raises on bad input."""
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def to_positive_int(value: Any, default: int = 2, *, minimum: int = 1) -> int:
    """Parse speaker count and similar; falls back to ``default`` on failure."""
    if value is None:
        return max(minimum, default)
    if isinstance(value, bool):
        return max(minimum, int(value))
    if isinstance(value, int):
        return max(minimum, value)
    if isinstance(value, float):
        return max(minimum, int(value))
    try:
        parsed = int(float(str(value).strip()))
        return max(minimum, parsed)
    except (ValueError, TypeError):
        return max(minimum, default)
