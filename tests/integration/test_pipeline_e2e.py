"""End-to-end pipeline integration test."""

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.audit.service import AuditService
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.user import User
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.bucket import InMemoryBucketClient
from ianuacare.infrastructure.storage.database import InMemoryDatabaseClient
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class IdentityModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"result": payload}


def test_full_pipeline_with_in_memory_infra() -> None:
    db = InMemoryDatabaseClient()
    bucket = InMemoryBucketClient()
    writer = Writer(db, bucket)
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"nlp": IdentityModel()},
        default_model_key="nlp",
    )
    pipe = Pipeline(
        DataManager(),
        DataValidator(),
        writer,
        Reader(db),
        orch,
        AuditService(db),
    )
    user = User("user-42", "clinician", ["pipeline:run"])
    ctx = RequestContext(user, "ianuacare-demo", metadata={"model_key": "nlp"})
    packet = pipe.run({"clinical_note": "non-phi fixture"}, ctx)

    assert packet.raw_data == {"clinical_note": "non-phi fixture"}
    assert packet.inference_result == {"result": {"clinical_note": "non-phi fixture"}}
    assert len(db.fetch_all("raw_records")) == 1
    assert len(db.fetch_all("processed_records")) == 1
    assert len(db.fetch_all("inference_results")) == 1
    assert len(db.fetch_all("audit_events")) >= 2
