"""Database and bucket clients."""

from ianuacare.infrastructure.storage.bucket import InMemoryBucketClient
from ianuacare.infrastructure.storage.database import InMemoryDatabaseClient


def test_database_write_fetch() -> None:
    db = InMemoryDatabaseClient()
    db.write("c", {"a": 1})
    assert db.fetch_all("c") == [{"a": 1}]


def test_database_crud_primitives() -> None:
    db = InMemoryDatabaseClient()
    db.create("patients", {"id": "p1", "name": "Ada", "status": "new"})
    db.create("patients", {"id": "p2", "name": "Lin", "status": "new"})

    assert db.read_one("patients", key="id", value="p1") == {"id": "p1", "name": "Ada", "status": "new"}
    assert db.read_many("patients", filters={"status": "new"}) == [
        {"id": "p1", "name": "Ada", "status": "new"},
        {"id": "p2", "name": "Lin", "status": "new"},
    ]

    assert db.update("patients", key="id", value="p1", updates={"status": "active"})["updated"] == 1
    assert db.read_one("patients", key="id", value="p1") == {"id": "p1", "name": "Ada", "status": "active"}

    assert db.delete("patients", key="id", value="p2")["deleted"] == 1
    assert db.read_one("patients", key="id", value="p2") is None


def test_bucket_upload_download() -> None:
    b = InMemoryBucketClient()
    b.upload("k", b"data")
    assert b.download("k") == b"data"
