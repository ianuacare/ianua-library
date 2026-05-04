"""Bucket pipeline (audio + text) via PipelineDatabase / Pipeline."""

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.audit.service import AuditService
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class StubModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"echo": payload}


def test_run_bucket_text_prepare_upload(db, bucket, context) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"stub": StubModel()},
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
    packet = pipe.run_bucket(
        "prepare_upload",
        {
            "collection": "text_assets",
            "filename": "notes.txt",
        },
        context,
        content_type="text",
    )
    assert packet.processed_data is not None
    assert "text_id" in packet.processed_data
    ok = packet.processed_data["object_key"]
    assert ok.endswith(".txt")
    assert "/text/" in ok


def test_run_audio_delegates_to_run_bucket(db, bucket, context) -> None:
    writer = Writer(db, bucket)
    reader = Reader(db)
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"stub": StubModel()},
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
    p_audio = pipe.run_audio(
        "prepare_upload",
        {"collection": "audio_assets", "filename": "a.wav"},
        context,
    )
    p_bucket = pipe.run_bucket(
        "prepare_upload",
        {"collection": "audio_assets", "filename": "b.wav"},
        context,
        content_type="audio",
    )
    assert p_audio.processed_data["object_key"].count("/audio/") == 1
    assert p_bucket.processed_data["object_key"].count("/audio/") == 1
