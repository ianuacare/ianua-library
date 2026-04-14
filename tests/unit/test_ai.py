"""AI layer."""

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.providers.callable import CallableProvider


class StubModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"stub": True, "payload": payload}


def test_ai_provider_default() -> None:
    p = CallableProvider()
    out = p.infer("m", {"x": 1})
    assert "model" in out or "result" in out or "echo" in str(out)


def test_nlp_model(provider: CallableProvider) -> None:
    m = NLPModel(provider, "clinical")
    r = m.run("hello")
    assert r is not None


def test_stub_model() -> None:
    s = StubModel()
    assert s.run({"a": 1})["stub"] is True
