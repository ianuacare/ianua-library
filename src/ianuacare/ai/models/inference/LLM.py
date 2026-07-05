"""LLM model built on top of NLP provider + normalizer."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider


def _payload_without_model_type(payload: Any) -> tuple[Any, str | None]:
    """Split optional ``model_type`` for routing (e.g. Together chat vs embeddings)."""
    if not isinstance(payload, dict):
        return payload, None
    mt = payload.get("model_type")
    if isinstance(mt, str) and mt.strip():
        trimmed = dict(payload)
        trimmed.pop("model_type", None)
        return trimmed, mt.strip().lower()
    return payload, None


class LLMModel(NLPModel):
    """Inference model for LLM text generation tasks.

    Generation parameters are set once at construction time and forwarded to the
    provider on every call via the generic ``params`` mapping. Only the
    parameters that are explicitly set (not ``None``) are sent, so unset knobs
    fall back to each model's own defaults. ``temperature`` and ``top_p`` carry
    safe built-in defaults; override them per model as needed.

    Reasoning is controlled with ``reasoning_effort`` (``"low" | "medium" |
    "high"``) and/or ``reasoning_enabled`` (toggle for hybrid models). Output
    shape is controlled with ``response_format`` (for example
    ``{"type": "json_object"}`` or a JSON-schema spec). Provider-specific knobs
    can be passed through ``extra`` (for example Together's
    ``chat_template_kwargs``).
    """

    def __init__(
        self,
        provider: AIProvider,
        model_name: str,
        normalizer: ModelOutNormalizer,
        *,
        temperature: float | None = 0.7,
        top_p: float | None = 1.0,
        top_k: int | None = None,
        max_tokens: int | None = None,
        stop: str | list[str] | None = None,
        seed: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        repetition_penalty: float | None = None,
        reasoning_effort: str | None = None,
        reasoning_enabled: bool | None = None,
        response_format: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(provider, model_name)
        self._normalizer = normalizer
        self._params = self._collect_params(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            stop=stop,
            seed=seed,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            reasoning_effort=reasoning_effort,
            reasoning_enabled=reasoning_enabled,
            response_format=response_format,
            extra=extra,
        )

    @staticmethod
    def _collect_params(**kwargs: Any) -> dict[str, Any]:
        """Keep only explicitly set generation params (drop ``None`` values)."""
        return {key: value for key, value in kwargs.items() if value is not None}

    @property
    def params(self) -> dict[str, Any]:
        """Read-only view of the generation params forwarded to the provider."""
        return dict(self._params)

    def run(self, payload: Any) -> dict[str, Any]:
        body, model_type = _payload_without_model_type(payload)
        raw = self._provider.infer(
            self._model_name, body, model_type=model_type, params=self._params
        )
        return self._normalizer.normalize_summary(raw)

    def stream(self, payload: Any) -> Iterator[str]:
        """Yield raw text fragments from the provider stream."""
        body, model_type = _payload_without_model_type(payload)
        yield from self._provider.infer_stream(
            self._model_name, body, model_type=model_type, params=self._params
        )

    async def arun(self, payload: Any) -> dict[str, Any]:
        body, model_type = _payload_without_model_type(payload)
        raw = await self._provider.ainfer(
            self._model_name, body, model_type=model_type, params=self._params
        )
        return self._normalizer.normalize_summary(raw)

    async def astream(self, payload: Any) -> AsyncIterator[str]:
        body, model_type = _payload_without_model_type(payload)
        async for chunk in self._provider.ainfer_stream(
            self._model_name, body, model_type=model_type, params=self._params
        ):
            yield chunk

    def finalize_stream_text(self, text: str) -> dict[str, Any]:
        """Normalize assembled streaming output the same way as :meth:`run`."""
        return self._normalizer.normalize_summary({"text": text})
