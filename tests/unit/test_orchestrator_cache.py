"""Orchestrator cache integration."""

import pytest
from pydantic import BaseModel

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.models.user import User
from ianuacare.core.orchestration import InputDataParser, Orchestrator, OutputDataParser
from ianuacare.infrastructure.cache import InMemoryCacheClient


class CounterModel(BaseAIModel):
    def __init__(self) -> None:
        self.calls = 0

    def run(self, payload: object) -> dict:
        self.calls += 1
        return {"payload": payload}


def test_orchestrator_uses_cache() -> None:
    model = CounterModel()
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"m": model},
        default_model_key="m",
        cache=InMemoryCacheClient(),
    )
    ctx = RequestContext(User("u1", "r", []), "prod", {"model_key": "m"})
    p1 = DataPacket(validated_data={"x": 1})
    p2 = DataPacket(validated_data={"x": 1})

    orch.execute(p1, ctx)
    orch.execute(p2, ctx)
    assert model.calls == 1


def test_orchestrator_applies_request_output_contract_on_cache_hits() -> None:
    class Result(BaseModel):
        label: str

    model = CounterModel()
    orchestrator = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"llm_example": model},
        cache=InMemoryCacheClient(),
    )
    user = User("u1", "r", [])
    payload = {"text": "hello"}

    # Rejecting a fresh response must not cache it.
    context = RequestContext(user, "prod", {"output_model": Result})
    with pytest.raises(ValidationError, match="label"):
        orchestrator.execute(DataPacket(validated_data=payload), context)

    def normalize(data: dict) -> dict:
        return {"label": data.pop("payload")["text"]}

    context.metadata["output_transform"] = normalize
    fresh = orchestrator.execute(DataPacket(validated_data=payload), context)

    context.metadata["output_transform"] = lambda data: {"label": data["payload"]["text"].upper()}
    cached = orchestrator.execute(DataPacket(validated_data=payload), context)

    assert model.calls == 2
    assert fresh.inference_result == cached.inference_result == {"payload": payload}
    assert fresh.processed_data == {"label": "hello"}
    assert cached.processed_data == {"label": "HELLO"}
