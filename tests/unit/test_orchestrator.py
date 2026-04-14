"""Orchestrator."""

import pytest

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, OrchestrationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.models.user import User
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import DataParser


class OkModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"out": payload}


class BadModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        raise RuntimeError("boom")


def test_execute_happy_path() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", metadata={"model_key": "m1"})
    p = DataPacket(raw_data=1, validated_data=1)
    orch = Orchestrator(DataParser(), {"m1": OkModel()}, default_model_key="m1")
    orch.execute(p, ctx)
    assert p.inference_result == {"out": 1}
    assert p.processed_data == {"out": 1}


def test_select_model_single() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", {})
    p = DataPacket(validated_data="x")
    orch = Orchestrator(DataParser(), {"only": OkModel()})
    orch.execute(p, ctx)
    assert p.inference_result is not None


def test_orchestration_no_model() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", {})
    p = DataPacket(validated_data="x")
    orch = Orchestrator(DataParser(), {})
    with pytest.raises(OrchestrationError):
        orch.execute(p, ctx)


def test_inference_error_wrapped() -> None:
    u = User("u1", "r", [])
    ctx = RequestContext(u, "p", metadata={"model_key": "bad"})
    p = DataPacket(validated_data="x")
    orch = Orchestrator(DataParser(), {"bad": BadModel()})
    with pytest.raises(InferenceError):
        orch.execute(p, ctx)
