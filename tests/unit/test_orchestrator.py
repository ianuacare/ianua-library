"""Orchestrator."""

import pytest

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, OrchestrationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.models.user import User
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser


class OkModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"out": payload}


class BadModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        raise RuntimeError("boom")


def _build_orchestrator(models: dict[str, BaseAIModel], **kwargs: object) -> Orchestrator:
    return Orchestrator(InputDataParser(), OutputDataParser(), models, **kwargs)  # type: ignore[arg-type]


def test_execute_happy_path() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", metadata={"model_key": "m1"})
    p = DataPacket(raw_data=1, validated_data=1)
    orch = _build_orchestrator({"m1": OkModel()}, default_model_key="m1")
    orch.execute(p, ctx)
    assert p.inference_result == {"out": 1}
    assert p.processed_data == {"out": 1}


def test_select_model_single() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", {})
    p = DataPacket(validated_data="x")
    orch = _build_orchestrator({"only": OkModel()})
    orch.execute(p, ctx)
    assert p.inference_result is not None


def test_orchestration_no_model() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", {})
    p = DataPacket(validated_data="x")
    orch = _build_orchestrator({})
    with pytest.raises(OrchestrationError):
        orch.execute(p, ctx)


def test_inference_error_wrapped() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", metadata={"model_key": "bad"})
    p = DataPacket(validated_data="x")
    orch = _build_orchestrator({"bad": BadModel()})
    with pytest.raises(InferenceError):
        orch.execute(p, ctx)


class LLMStubModel(BaseAIModel):
    def __init__(self, output: dict) -> None:
        self._output = output

    def run(self, payload: object) -> dict:
        return dict(self._output)


def test_execute_llm_with_output_schema_passes() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(
        u,
        "p",
        metadata={
            "model_key": "llm",
            "output_schema": {
                "required": ["summary"],
                "properties": {"summary": {"type": "string"}},
            },
        },
    )
    p = DataPacket(validated_data={"text": "hello"})
    orch = _build_orchestrator({"llm": LLMStubModel({"summary": "ciao"})})
    orch.execute(p, ctx)
    assert p.processed_data == {"summary": "ciao"}


def test_execute_llm_with_output_schema_missing_field_raises() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(
        u,
        "p",
        metadata={
            "model_key": "llm",
            "output_schema": {"required": ["summary", "score"]},
        },
    )
    p = DataPacket(validated_data={"text": "hello"})
    orch = _build_orchestrator({"llm": LLMStubModel({"summary": "ciao"})})
    from ianuacare.core.exceptions.errors import ValidationError

    with pytest.raises(ValidationError):
        orch.execute(p, ctx)


def test_execute_invalid_output_schema_type_raises() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", metadata={"model_key": "llm", "output_schema": "not-a-dict"})
    p = DataPacket(validated_data={"text": "hello"})
    orch = _build_orchestrator({"llm": LLMStubModel({"summary": "ciao"})})
    with pytest.raises(OrchestrationError):
        orch.execute(p, ctx)
