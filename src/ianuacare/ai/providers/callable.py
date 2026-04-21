"""Callable-backed provider for tests and quick integrations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ianuacare.ai.providers.base import AIProvider


class CallableProvider(AIProvider):
    """Delegate inference to an injected callable."""

    def __init__(self, infer_fn: Callable[[str, Any], Any] | None = None) -> None:
        self._infer = infer_fn or self._default_infer

    def infer(self, model_name: str, payload: Any, *, model_type: str | None = None) -> Any:
        _ = model_type
        return self._infer(model_name, payload)

    @staticmethod
    def _default_infer(model_name: str, payload: Any) -> dict[str, Any]:
        return {"model": model_name, "echo": payload}
