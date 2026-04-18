"""Orchestrator cache integration."""

from ianuacare.ai.models.inference.base import BaseAIModel
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
