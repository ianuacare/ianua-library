"""Writer."""

import pytest

from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.models.user import User
from ianuacare.infrastructure.storage.writer import Writer


def test_write_roundtrip(db, bucket) -> None:
    w = Writer(db, bucket)
    u = User("u1", "r", [])
    ctx = RequestContext(u, "prod", {})
    p = DataPacket(
        raw_data={"a": 1},
        processed_data={"b": 2},
        inference_result={"c": 3},
        metadata={"request_id": "r1"},
    )
    assert w.write_raw(p, ctx)["ok"] is True
    assert w.write_processed(p, ctx)["ok"] is True
    assert w.write_result(p, ctx)["ok"] is True
    assert w.write_log("event", ctx)["ok"] is True


def test_writer_crud_write_methods(db, bucket) -> None:
    w = Writer(db, bucket)
    u = User("u1", "r", [])
    ctx = RequestContext(u, "prod", {})

    created = w.write_create("patients", {"id": "p1", "name": "Ada"}, ctx)
    assert created["ok"] is True
    record_after_create = db.read_one("patients", key="id", value="p1")
    assert record_after_create["id"] == "p1"
    assert record_after_create["name"] == "Ada"
    assert record_after_create["product"] == "prod"
    assert record_after_create["user_id"] == "u1"
    assert record_after_create["created_at"] == record_after_create["updated_at"]
    initial_created_at = record_after_create["created_at"]

    updated = w.write_update(
        "patients",
        lookup_field="id",
        lookup_value="p1",
        updates={"name": "Ada Lovelace"},
        context=ctx,
    )
    assert updated["updated"] == 1
    record_after_update = db.read_one("patients", key="id", value="p1")
    assert record_after_update["name"] == "Ada Lovelace"
    assert record_after_update["created_at"] == initial_created_at
    assert isinstance(record_after_update["updated_at"], str)

    deleted = w.write_delete(
        "patients",
        lookup_field="id",
        lookup_value="p1",
        context=ctx,
    )
    assert deleted["deleted"] == 1


# ---------------------------------------------------------------------------
# write_bucket_direct_upload – upsert behaviour
# ---------------------------------------------------------------------------

def test_bucket_direct_upload_inserts_when_no_reference_exists(db, bucket) -> None:
    """Fresh direct upload (no prior reference row) must INSERT the record."""
    w = Writer(db, bucket)
    ctx = RequestContext(User("u1", "r", []), "prod", {})

    result = w.write_bucket_direct_upload(
        collection="audio_records",
        payload={
            "audio_id": "ses_abc",
            "request_id": "ses_abc",
            "filename": "ses_abc.wav",
            "content": b"RIFF\x00\x00\x00\x00",
        },
        context=ctx,
        content_type="audio",
    )

    assert result["status"] == "uploaded"
    assert result["audio_id"] == "ses_abc"
    row = db.read_one("audio_records", key="audio_id", value="ses_abc")
    assert row is not None
    assert row["status"] == "uploaded"
    assert len(db.read_many("audio_records")) == 1


def test_bucket_direct_upload_updates_when_reference_already_exists(db, bucket) -> None:
    """When prepare_upload already created the reference row, direct upload must UPDATE
    (not INSERT), preventing the duplicate-key violation on audio_records PRIMARY KEY."""
    w = Writer(db, bucket)
    ctx = RequestContext(User("u1", "r", []), "prod", {})

    # Simulate what write_bucket_upload_reference does: a pending_upload row exists.
    db.create(
        "audio_records",
        {
            "audio_id": "ses_xyz",
            "content_type": "audio",
            "user_id": "u1",
            "product": "prod",
            "status": "pending_upload",
            "filename": "ses_xyz.wav",
            "mime_type": "audio/wav",
            "size_bytes": None,
            "bucket": "my-bucket",
            "object_key": "prod/u1/audio/ses_xyz.wav",
            "request_id": "ses_xyz",
        },
    )
    assert len(db.read_many("audio_records")) == 1

    result = w.write_bucket_direct_upload(
        collection="audio_records",
        payload={
            "audio_id": "ses_xyz",
            "request_id": "ses_xyz",
            "filename": "ses_xyz.wav",
            "content": b"RIFF\x00\x00\x00\x00",
        },
        context=ctx,
        content_type="audio",
    )

    assert result["status"] == "uploaded"
    # Exactly one row must remain — no duplicate inserted.
    rows = db.read_many("audio_records")
    assert len(rows) == 1
    assert rows[0]["status"] == "uploaded"
    assert rows[0]["size_bytes"] == len(b"RIFF\x00\x00\x00\x00")
