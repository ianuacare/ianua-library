"""Together AI provider adapter."""

from __future__ import annotations

from typing import Any

try:  # Optional dependency
    from together import Together
except Exception:  # pragma: no cover - optional import
    Together = None  # type: ignore[assignment]

from ianuacare.ai.providers.base import AIProvider


class TogetherAIProvider(AIProvider):
    """Provider implementation backed by Together chat completions."""

    def __init__(self, api_key: str, default_model: str) -> None:
        if Together is None:
            raise ImportError("TogetherAIProvider requires together")
        self._client = Together(api_key=api_key)
        self._default_model = default_model

    def infer(self, model_name: str, payload: Any) -> dict[str, Any]:
        selected_model = model_name or self._default_model
        response = self._client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": str(payload)}],
        )
        choice = response.choices[0]
        return {
            "model": selected_model,
            "content": choice.message.content,
            "raw": response.model_dump(),
        }
