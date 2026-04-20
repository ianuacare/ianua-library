"""Read CRUD records from database storage."""

from __future__ import annotations

from typing import Any

from ianuacare.core.exceptions.errors import StorageError, ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.infrastructure.storage.bucket import BucketClient
from ianuacare.infrastructure.storage.database import DatabaseClient
from ianuacare.infrastructure.storage.vector import VectorDatabaseClient


_VALID_LEVELS: frozenset[str] = frozenset({"text", "sentence", "words"})


class Reader:
    """Reads domain records through the configured ``DatabaseClient``."""

    def __init__(
        self,
        db_client: DatabaseClient,
        bucket_client: BucketClient | None = None,
        vector_client: VectorDatabaseClient | None = None,
    ) -> None:
        self._db = db_client
        self._bucket = bucket_client
        self._vector = vector_client

    def read_one(
        self,
        collection: str,
        *,
        lookup_field: str,
        lookup_value: Any,
        context: RequestContext,
    ) -> dict[str, Any] | None:
        """Read one record by a lookup field/value pair."""
        try:
            _ = context  # keeps a uniform interface with Writer methods
            return self._db.read_one(
                collection,
                key=lookup_field,
                value=lookup_value,
            )
        except Exception as exc:
            raise StorageError("Failed to read one record") from exc

    def read_many(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None,
        context: RequestContext,
    ) -> list[dict[str, Any]]:
        """Read many records using exact-match filters."""
        try:
            _ = context  # keeps a uniform interface with Writer methods
            return self._db.read_many(collection, filters=filters)
        except Exception as exc:
            raise StorageError("Failed to read records") from exc

    def read_vector_search(
        self,
        collection: str,
        *,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any],
        score_threshold: float | None = None,
        context: RequestContext,
    ) -> list[dict[str, Any]]:
        """Search the vector collection restricted to ``filters['level']``.

        ``filters`` is required and must contain a ``level`` key whose value
        is one of ``text``, ``sentence``, ``words`` (the levels produced by
        the ``text_embedder`` pipeline). Additional keys in ``filters`` are
        forwarded as exact-match conditions to the backend.
        """
        if self._vector is None:
            raise StorageError("vector_client is not configured on Reader")
        _ = context
        if not isinstance(filters, dict) or "level" not in filters:
            raise ValidationError("filters.level is required for vector search")
        if filters["level"] not in _VALID_LEVELS:
            raise ValidationError(
                f"filters.level must be one of {sorted(_VALID_LEVELS)}"
            )
        if not isinstance(vector, list) or not vector:
            raise ValidationError("vector must be a non-empty list of floats")
        try:
            return self._vector.search(
                collection,
                vector=vector,
                top_k=top_k,
                filters=dict(filters),
                score_threshold=score_threshold,
            )
        except Exception as exc:
            raise StorageError("Failed to search vector points") from exc

    def read_audio(
        self,
        collection: str,
        *,
        lookup_field: str,
        lookup_value: Any,
        context: RequestContext,
    ) -> dict[str, Any] | None:
        """Read one audio record and enrich it with a presigned download URL."""
        try:
            _ = context
            record = self._db.read_one(collection, key=lookup_field, value=lookup_value)
            if record is None:
                return None
            object_key = record.get("object_key")
            if not isinstance(object_key, str) or not object_key:
                return {**record, "download_url": None}
            generator = getattr(self._bucket, "generate_presigned_download_url", None)
            if not callable(generator):
                return {**record, "download_url": None}
            expires_in = int(record.get("download_url_expires_in") or 3600)
            download_url = str(generator(object_key, expires_in=expires_in))
            return {**record, "download_url": download_url}
        except Exception as exc:
            raise StorageError("Failed to read audio record") from exc
