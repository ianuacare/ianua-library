"""Database abstraction (protocol + in-memory implementation)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DatabaseClient(Protocol):
    """Contract for database-backed persistence."""

    def create(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        """Create a record in ``collection``."""
        ...

    def read_one(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
    ) -> dict[str, Any] | None:
        """Return the first matching record by ``key`` or ``None``."""
        ...

    def read_many(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all records in ``collection`` filtered by exact-match pairs."""
        ...

    def update(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update records matching ``key == value`` with ``updates``."""
        ...

    def delete(self, collection: str, *, key: str, value: Any) -> dict[str, Any]:
        """Delete records matching ``key == value``."""
        ...

    def write(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        """Insert or update a record in ``collection``."""
        ...

    def fetch_all(self, collection: str) -> list[dict[str, Any]]:
        """Return all records in ``collection``."""
        ...


class InMemoryDatabaseClient:
    """In-memory ``DatabaseClient`` for development and tests."""

    def __init__(self, storage: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._storage: dict[str, list[dict[str, Any]]] = storage if storage is not None else {}

    def create(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        if collection not in self._storage:
            self._storage[collection] = []
        self._storage[collection].append(dict(record))
        return {"ok": True, "collection": collection, "count": len(self._storage[collection])}

    def read_one(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
    ) -> dict[str, Any] | None:
        for record in self._storage.get(collection, []):
            if record.get(key) == value:
                return dict(record)
        return None

    def read_many(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not filters:
            return [dict(r) for r in self._storage.get(collection, [])]
        results: list[dict[str, Any]] = []
        for record in self._storage.get(collection, []):
            if all(record.get(k) == v for k, v in filters.items()):
                results.append(dict(record))
        return results

    def update(
        self,
        collection: str,
        *,
        key: str,
        value: Any,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        updated = 0
        for record in self._storage.get(collection, []):
            if record.get(key) == value:
                record.update(updates)
                updated += 1
        return {"ok": True, "collection": collection, "updated": updated}

    def delete(self, collection: str, *, key: str, value: Any) -> dict[str, Any]:
        existing = self._storage.get(collection, [])
        kept = [r for r in existing if r.get(key) != value]
        deleted = len(existing) - len(kept)
        self._storage[collection] = kept
        return {"ok": True, "collection": collection, "deleted": deleted}

    def write(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        return self.create(collection, record)

    def fetch_all(self, collection: str) -> list[dict[str, Any]]:
        return self.read_many(collection)

