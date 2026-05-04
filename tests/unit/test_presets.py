"""Preset factory."""

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.auth.repository import UserRepository
from ianuacare.infrastructure.storage import InMemoryBucketClient, InMemoryDatabaseClient
from ianuacare.presets import create_stack


class EchoModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"echo": payload}


def test_create_stack_wires_core_services() -> None:
    stack = create_stack(
        auth_repository=UserRepository(),
        database=InMemoryDatabaseClient(),
        bucket=InMemoryBucketClient(),
        models={"m": EchoModel()},
        default_model_key="m",
    )
    assert stack.auth_service is not None
    assert stack.pipeline is not None
    assert stack.pipeline_model is stack.pipeline.model
    assert stack.pipeline_database is stack.pipeline.database
    assert stack.orchestrator is not None
    assert stack.writer is not None
