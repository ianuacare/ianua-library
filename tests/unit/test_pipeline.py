"""Pipeline unit tests."""

from ianuacare.ai.base import BaseAIModel
from ianuacare.core.audit.service import AuditService
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import DataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class EchoModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"echo": payload}


def test_pipeline_run_end_to_end(db, bucket, context) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        DataParser(),
        {"stub": EchoModel()},
        default_model_key="stub",
    )
    context.metadata["model_key"] = "stub"
    pipe = Pipeline(
        DataManager(),
        DataValidator(),
        writer,
        reader,
        orch,
        AuditService(db),
    )
    packet = pipe.run({"text": "hello"}, context)
    assert packet.inference_result is not None
    assert packet.inference_result["echo"] == {"text": "hello"}
    assert len(db.fetch_all("audit_events")) >= 2


def test_pipeline_run_model_explicit(db, bucket, context) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        DataParser(),
        {"stub": EchoModel()},
        default_model_key="stub",
    )
    pipe = Pipeline(
        DataManager(),
        DataValidator(),
        writer,
        reader,
        orch,
        AuditService(db),
    )

    packet = pipe.run_model({"text": "model-flow"}, context)
    assert packet.inference_result == {"echo": {"text": "model-flow"}}


def test_pipeline_run_crud_write_and_read(db, bucket, context) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        DataParser(),
        {"stub": EchoModel()},
        default_model_key="stub",
    )
    pipe = Pipeline(
        DataManager(),
        DataValidator(),
        writer,
        reader,
        orch,
        AuditService(db),
    )

    created = pipe.run_crud(
        "create",
        {"collection": "patients", "record": {"id": "p1", "name": "Ada"}},
        context,
    )
    assert created.processed_data["ok"] is True

    updated = pipe.run_crud(
        "update",
        {
            "collection": "patients",
            "lookup_field": "id",
            "lookup_value": "p1",
            "updates": {"name": "Ada Lovelace"},
        },
        context,
    )
    assert updated.processed_data["updated"] == 1

    read_one = pipe.run_crud(
        "read_one",
        {"collection": "patients", "lookup_field": "id", "lookup_value": "p1"},
        context,
    )
    assert read_one.processed_data == {
        "id": "p1",
        "name": "Ada Lovelace",
        "product": context.product,
        "user_id": context.user.user_id,
    }

    read_many = pipe.run_crud(
        "read_many",
        {"collection": "patients", "filters": {"user_id": context.user.user_id}},
        context,
    )
    assert read_many.processed_data == [read_one.processed_data]
