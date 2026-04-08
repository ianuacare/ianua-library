"""PostgreSQL storage adapter with real relational columns."""

from __future__ import annotations

import datetime
import json
from typing import Any

try:  # Optional dependency
    import psycopg
    from psycopg import sql
except Exception:  # pragma: no cover - import-time optional dependency handling
    psycopg = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]


class PostgresDatabaseClient:
    """Persist records in per-collection PostgreSQL tables with real columns."""

    def __init__(self, connection_string: str) -> None:
        if psycopg is None:
            raise ImportError("PostgresDatabaseClient requires psycopg")
        self._connection_string = connection_string

    # -- CRUD primitives ------------------------------------------------

    def create(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        self._ensure_table(collection, record)
        self._ensure_columns(collection, record)
        columns = list(record.keys())
        values = [self._serialize(record[c]) for c in columns]
        query = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({phs})").format(
            table=sql.Identifier(collection),
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            phs=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()
        return {"ok": True, "collection": collection}

    def read_one(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
    ) -> dict[str, Any] | None:
        query = sql.SQL(
            "SELECT * FROM {table} WHERE {col} = %s LIMIT 1"
        ).format(
            table=sql.Identifier(collection),
            col=sql.Identifier(key),
        )
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query, (self._serialize(value),))
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))

    def read_many(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not filters:
            query = sql.SQL("SELECT * FROM {table}").format(
                table=sql.Identifier(collection),
            )
            params: tuple[Any, ...] = ()
        else:
            clauses = sql.SQL(" AND ").join(
                sql.SQL("{col} = %s").format(col=sql.Identifier(k))
                for k in filters
            )
            query = sql.SQL("SELECT * FROM {table} WHERE {where}").format(
                table=sql.Identifier(collection),
                where=clauses,
            )
            params = tuple(self._serialize(v) for v in filters.values())
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, r)) for r in rows]

    def update(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_columns(collection, updates)
        set_clause = sql.SQL(", ").join(
            sql.SQL("{col} = %s").format(col=sql.Identifier(k))
            for k in updates
        )
        query = sql.SQL("UPDATE {table} SET {sets} WHERE {col} = %s").format(
            table=sql.Identifier(collection),
            sets=set_clause,
            col=sql.Identifier(key),
        )
        params = [self._serialize(v) for v in updates.values()]
        params.append(self._serialize(value))
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            updated = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
        return {"ok": True, "collection": collection, "updated": updated}

    def delete(self, collection: str, *, key: str, value: Any) -> dict[str, Any]:
        query = sql.SQL("DELETE FROM {table} WHERE {col} = %s").format(
            table=sql.Identifier(collection),
            col=sql.Identifier(key),
        )
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query, (self._serialize(value),))
            deleted = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
        return {"ok": True, "collection": collection, "deleted": deleted}

    # -- Legacy compatibility -------------------------------------------

    def write(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        return self.create(collection, record)

    def fetch_all(self, collection: str) -> list[dict[str, Any]]:
        return self.read_many(collection)

    # -- Internal helpers -----------------------------------------------

    def _ensure_table(self, collection: str, record: dict[str, Any]) -> None:
        """Create the table if it does not exist, inferring column types from *record*."""
        col_defs = sql.SQL(", ").join(
            sql.SQL("{col} {type}").format(
                col=sql.Identifier(k),
                type=sql.SQL(self._pg_type(v)),
            )
            for k, v in record.items()
        )
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} ({cols})"
        ).format(
            table=sql.Identifier(collection),
            cols=col_defs,
        )
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            cur.execute(query)
            conn.commit()

    def _ensure_columns(self, collection: str, fields: dict[str, Any]) -> None:
        """Add columns that don't yet exist in the table."""
        with psycopg.connect(self._connection_string) as conn, conn.cursor() as cur:
            for col_name, sample_value in fields.items():
                alter_query = sql.SQL(
                    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {type}"
                ).format(
                    table=sql.Identifier(collection),
                    col=sql.Identifier(col_name),
                    type=sql.SQL(self._pg_type(sample_value)),
                )
                try:
                    cur.execute(alter_query)
                except Exception:
                    pass
            conn.commit()

    @staticmethod
    def _pg_type(value: Any) -> str:
        """Map a Python value to a PostgreSQL column type."""
        if isinstance(value, bool):
            return "BOOLEAN"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "DOUBLE PRECISION"
        if isinstance(value, bytes):
            return "BYTEA"
        if isinstance(value, datetime.datetime):
            return "TIMESTAMPTZ"
        if isinstance(value, datetime.date):
            return "DATE"
        if isinstance(value, (dict, list)):
            return "JSONB"
        return "TEXT"

    @staticmethod
    def _serialize(value: Any) -> Any:
        """Prepare a Python value for a parameterized query."""
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str)
        return value
