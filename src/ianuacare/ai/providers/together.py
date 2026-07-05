"""Together AI provider adapter."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

try:  # Optional dependency
    from together import Together
except Exception:  # pragma: no cover - optional import
    Together = None  # type: ignore[assignment]

from ianuacare.ai.providers.base import AIProvider


def _embedding_mode(model_type: str | None) -> bool:
    if model_type is None:
        return False
    mt = model_type.strip().lower()
    return mt in ("embedding", "embeddings")


# Generic generation params forwarded verbatim to the Together SDK.
_PASS_THROUGH_PARAMS: tuple[str, ...] = (
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "stop",
    "seed",
    "frequency_penalty",
    "presence_penalty",
    "repetition_penalty",
    "response_format",
    "reasoning_effort",
)


def _to_together_kwargs(params: dict[str, Any] | None) -> dict[str, Any]:
    """Map the generic ``params`` mapping onto Together chat completion kwargs.

    Pass-through keys go straight to the SDK. ``reasoning_enabled`` becomes the
    ``reasoning={"enabled": bool}`` toggle for hybrid models, and ``extra`` is
    spread for provider-specific knobs (for example ``chat_template_kwargs``).
    """
    if not params:
        return {}
    kwargs: dict[str, Any] = {}
    for key in _PASS_THROUGH_PARAMS:
        if params.get(key) is not None:
            kwargs[key] = params[key]
    reasoning_enabled = params.get("reasoning_enabled")
    if reasoning_enabled is not None:
        kwargs["reasoning"] = {"enabled": bool(reasoning_enabled)}
    extra = params.get("extra")
    if isinstance(extra, dict):
        kwargs.update(extra)
    return kwargs


class TogetherAIProvider(AIProvider):
    """Provider backed by Together chat completions and embeddings."""

    def __init__(
        self,
        api_key: str,
        default_model: str,
        *,
        default_params: dict[str, Any] | None = None,
    ) -> None:
        if Together is None:
            raise ImportError("TogetherAIProvider requires together")
        self._client = Together(api_key=api_key)
        self._default_model = default_model
        self._default_params = dict(default_params) if default_params else {}

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if _embedding_mode(model_type):
            return self._infer_embeddings(model_name, payload)
        return self._infer_chat(model_name, payload, params=params)

    def infer_stream(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        if _embedding_mode(model_type):
            raise TypeError("TogetherAIProvider does not stream embedding requests")
        yield from super().infer_stream(
            model_name, payload, model_type=model_type, params=params
        )

    def _merge_params(self, params: dict[str, Any] | None) -> dict[str, Any]:
        """Combine constructor defaults with per-call params (per-call wins)."""
        if not self._default_params:
            return dict(params) if params else {}
        merged = dict(self._default_params)
        if params:
            merged.update(params)
        return merged

    def _infer_chat(
        self, model_name: str, payload: Any, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        selected_model = model_name or self._default_model
        # Accept a pre-built OpenAI-style messages list (produced by the chatbot
        # layer) or fall back to wrapping arbitrary payloads in a single user turn.
        if isinstance(payload, list):
            messages: list[Any] = payload
        else:
            messages = [{"role": "user", "content": str(payload)}]
        generation_kwargs = _to_together_kwargs(self._merge_params(params))
        response = self._client.chat.completions.create(
            model=selected_model,
            messages=messages,
            **generation_kwargs,
        )
        choice = response.choices[0]
        message = choice.message
        # Downstream normalizers read the ``text`` key; expose it here so chat
        # completions are not silently dropped. Reasoning models may leave
        # ``content`` empty and put the answer in ``reasoning`` — fall back to it.
        text = (message.content or "").strip()
        if not text:
            text = (getattr(message, "reasoning", None) or "").strip()
        return {
            "model": selected_model,
            "text": text,
            "content": message.content,
            "raw": response.model_dump(),
        }

    def _infer_embeddings(self, model_name: str, payload: Any) -> list[list[float]]:
        selected_model = model_name or self._default_model
        if isinstance(payload, str):
            inputs: str | list[str] = payload
        elif isinstance(payload, list) and all(isinstance(x, str) for x in payload):
            inputs = payload
        else:
            raise TypeError(
                "Together embedding payload must be str or list[str], got "
                f"{type(payload).__name__}"
            )
        response = self._client.embeddings.create(model=selected_model, input=inputs)
        rows = sorted(response.data or [], key=lambda row: row.index)
        return [list(row.embedding) for row in rows]
