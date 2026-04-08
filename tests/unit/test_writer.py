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
    assert db.read_one("patients", key="id", value="p1") == {
        "id": "p1",
        "name": "Ada",
        "product": "prod",
        "user_id": "u1",
    }

    updated = w.write_update(
        "patients",
        lookup_field="id",
        lookup_value="p1",
        updates={"name": "Ada Lovelace"},
        context=ctx,
    )
    assert updated["updated"] == 1
    assert db.read_one("patients", key="id", value="p1") == {
        "id": "p1",
        "name": "Ada Lovelace",
        "product": "prod",
        "user_id": "u1",
    }

    deleted = w.write_delete(
        "patients",
        lookup_field="id",
        lookup_value="p1",
        context=ctx,
    )
    assert deleted["deleted"] == 1
