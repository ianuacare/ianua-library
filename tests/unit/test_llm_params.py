"""Tests for LLMModel construction-time generation parameters."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.LLM import LLMModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider


class _RecordingProvider(AIProvider):
    """Provider that records the ``params`` it receives on the last call."""

    def __init__(self) -> None:
        self.last_params: dict[str, Any] | None = None

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self.last_params = params
        return {"text": "ok"}


def test_llm_model_has_default_temperature_and_top_p() -> None:
    provider = _RecordingProvider()
    model = LLMModel(provider, "m", ModelOutNormalizer())

    assert model.params == {"temperature": 0.7, "top_p": 1.0}


def test_llm_model_omits_unset_params() -> None:
    provider = _RecordingProvider()
    model = LLMModel(provider, "m", ModelOutNormalizer())

    assert "max_tokens" not in model.params
    assert "reasoning_effort" not in model.params
    assert "response_format" not in model.params


def test_llm_model_collects_set_params() -> None:
    provider = _RecordingProvider()
    model = LLMModel(
        provider,
        "m",
        ModelOutNormalizer(),
        temperature=0.2,
        top_p=0.9,
        max_tokens=256,
        reasoning_effort="medium",
        reasoning_enabled=True,
        response_format={"type": "json_object"},
        extra={"chat_template_kwargs": {"thinking": True}},
    )

    assert model.params == {
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 256,
        "reasoning_effort": "medium",
        "reasoning_enabled": True,
        "response_format": {"type": "json_object"},
        "extra": {"chat_template_kwargs": {"thinking": True}},
    }


def test_llm_model_can_disable_defaulted_params() -> None:
    provider = _RecordingProvider()
    model = LLMModel(provider, "m", ModelOutNormalizer(), temperature=None, top_p=None)

    assert model.params == {}


def test_llm_model_forwards_params_to_provider() -> None:
    provider = _RecordingProvider()
    model = LLMModel(provider, "m", ModelOutNormalizer(), temperature=0.3)

    model.run({"text": "hi"})

    assert provider.last_params == {"temperature": 0.3, "top_p": 1.0}


def test_llm_model_params_property_is_a_copy() -> None:
    provider = _RecordingProvider()
    model = LLMModel(provider, "m", ModelOutNormalizer())

    snapshot = model.params
    snapshot["temperature"] = 999

    assert model.params["temperature"] == 0.7
