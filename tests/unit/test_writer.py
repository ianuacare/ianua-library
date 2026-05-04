"""Writer."""

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
