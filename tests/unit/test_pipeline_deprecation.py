"""Pipeline facade emits DeprecationWarning on direct construction."""

import warnings

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.audit.service import AuditService
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class _Echo(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"echo": payload}


def test_pipeline_facade_emits_deprecation_warning(db, bucket) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"stub": _Echo()},
        default_model_key="stub",
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        Pipeline(
            DataManager(),
            DataValidator(),
            writer,
            reader,
            orch,
            AuditService(db),
        )
    assert any(
        issubclass(w.category, DeprecationWarning)
        and "Pipeline is deprecated" in str(w.message)
        for w in captured
    )
