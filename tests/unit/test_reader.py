"""Reader."""

from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.user import User
from ianuacare.infrastructure.storage.reader import Reader


def test_reader_read_one_and_many(db) -> None:
    db.create("patients", {"id": "p1", "name": "Ada", "status": "active"})
    db.create("patients", {"id": "p2", "name": "Lin", "status": "active"})
    db.create("patients", {"id": "p3", "name": "Max", "status": "inactive"})

    reader = Reader(db)
    ctx = RequestContext(User("u1", "r", []), "prod", {})

    one = reader.read_one("patients", lookup_field="id", lookup_value="p1", context=ctx)
    assert one == {"id": "p1", "name": "Ada", "status": "active"}

    many = reader.read_many("patients", filters={"status": "active"}, context=ctx)
    assert many == [
        {"id": "p1", "name": "Ada", "status": "active"},
        {"id": "p2", "name": "Lin", "status": "active"},
    ]
