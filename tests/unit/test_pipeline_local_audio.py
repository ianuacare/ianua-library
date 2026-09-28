"""Local bucket materialization remains a storage read operation."""

from pathlib import Path

import pytest

from ianuacare.core.audit.service import AuditService
from ianuacare.core.exceptions.errors import StorageError, ValidationError
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline_database import PipelineDatabase
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


@pytest.mark.parametrize("explicit", [True, False])
def test_retrieve_to_local(db, bucket, context, tmp_path, explicit):
    writer = Writer(db, bucket)
    writer.write_create("audio", {"id": "a", "object_key": "a.wav"}, context)
    bucket.upload("a.wav", b"audio content")
    events = []

    class Output:
        def after_read(self, packet, **kwargs):
            events.append(kwargs["operation"])

    pipe = PipelineDatabase(
        DataManager(),
        DataValidator(),
        writer,
        Reader(db, bucket),
        AuditService(db),
        output_parser=Output(),
    )
    payload = {"collection": "audio", "lookup_field": "id", "lookup_value": "a"}
    if explicit:
        payload["local_path"] = str(tmp_path / "saved.wav")
    result = pipe.run_bucket(
        "retrieve_to_local", payload, context, content_type="audio"
    ).processed_data
    path = Path(result["audio_path"])
    try:
        assert path.is_absolute()
        assert path.read_bytes() == b"audio content"
        assert result["object_key"] == "a.wav"
        assert events == ["retrieve_to_local"]
    finally:
        path.unlink()


def test_local_missing_and_existing_destination(db, bucket, context, tmp_path):
    reader = Reader(db, bucket)
    kwargs = {"lookup_field": "id", "lookup_value": "a", "context": context}
    assert reader.read_bucket_to_local("audio", **kwargs) is None
    Writer(db, bucket).write_create("audio", {"id": "a", "object_key": "a.wav"}, context)
    destination = tmp_path / "existing.wav"
    destination.write_bytes(b"keep")
    bucket.upload("a.wav", b"new")
    with pytest.raises(StorageError):
        reader.read_bucket_to_local("audio", local_path=str(destination), **kwargs)
    assert destination.read_bytes() == b"keep"


@pytest.mark.parametrize("content_type", ["audio", "text"])
def test_local_path_validation(content_type):
    with pytest.raises(ValidationError, match="local_path"):
        DataValidator().validate_bucket_payload(
            {"collection": "a", "lookup_field": "id", "lookup_value": "1", "local_path": 123},
            content_type=content_type,
            operation="retrieve_to_local",
        )
