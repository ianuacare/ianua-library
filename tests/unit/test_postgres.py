"""PostgreSQL adapter."""

from unittest.mock import MagicMock, patch

import ianuacare.infrastructure.storage.postgres as postgres_module
from ianuacare.infrastructure.storage.postgres import PostgresDatabaseClient


def _make_mocks():
    mock_psycopg = MagicMock()
    mock_sql = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    mock_psycopg.connect.return_value.__enter__.return_value = conn
    return mock_psycopg, mock_sql, conn, cur


def test_postgres_write_fetch() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.description = [("a",)]
    cur.fetchall.return_value = [(1,)]

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        out = db.write("records", {"a": 1})
        assert out["ok"] is True
        rows = db.fetch_all("records")
        assert rows == [{"a": 1}]


def test_postgres_create_uses_real_columns() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        out = db.create("patients", {"id": "p1", "name": "Ada"})
        assert out["ok"] is True
        assert cur.execute.called


def test_postgres_read_one() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.description = [("id",), ("name",)]
    cur.fetchone.return_value = ("p1", "Ada")

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        row = db.read_one("patients", key="id", value="p1")
        assert row == {"id": "p1", "name": "Ada"}


def test_postgres_read_one_not_found() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.fetchone.return_value = None

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        assert db.read_one("patients", key="id", value="missing") is None


def test_postgres_read_many_with_filters() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.description = [("id",), ("name",), ("status",)]
    cur.fetchall.return_value = [("p1", "Ada", "active"), ("p2", "Lin", "active")]

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        rows = db.read_many("patients", filters={"status": "active"})
        assert rows == [
            {"id": "p1", "name": "Ada", "status": "active"},
            {"id": "p2", "name": "Lin", "status": "active"},
        ]


def test_postgres_update() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.rowcount = 1

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        out = db.update("patients", key="id", value="p1", updates={"name": "Ada L"})
        assert out["updated"] == 1


def test_postgres_delete() -> None:
    mock_psycopg, mock_sql, conn, cur = _make_mocks()
    cur.rowcount = 1

    with (
        patch.object(postgres_module, "psycopg", mock_psycopg),
        patch.object(postgres_module, "sql", mock_sql),
    ):
        db = PostgresDatabaseClient("postgresql://example")
        out = db.delete("patients", key="id", value="p1")
        assert out["deleted"] == 1


def test_pg_type_mapping() -> None:
    import datetime

    assert PostgresDatabaseClient._pg_type(True) == "BOOLEAN"
    assert PostgresDatabaseClient._pg_type(42) == "INTEGER"
    assert PostgresDatabaseClient._pg_type(3.14) == "DOUBLE PRECISION"
    assert PostgresDatabaseClient._pg_type(b"bytes") == "BYTEA"
    assert PostgresDatabaseClient._pg_type(datetime.datetime.now()) == "TIMESTAMPTZ"
    assert PostgresDatabaseClient._pg_type(datetime.date.today()) == "DATE"
    assert PostgresDatabaseClient._pg_type({"a": 1}) == "JSONB"
    assert PostgresDatabaseClient._pg_type([1, 2]) == "JSONB"
    assert PostgresDatabaseClient._pg_type("hello") == "TEXT"
    assert PostgresDatabaseClient._pg_type(None) == "TEXT"
