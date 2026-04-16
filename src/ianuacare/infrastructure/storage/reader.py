"""Read CRUD records from database storage."""

from __future__ import annotations

from typing import Any

from ianuacare.core.exceptions.errors import StorageError
from ianuacare.core.models.context import RequestContext
from ianuacare.infrastructure.storage.bucket import BucketClient
from ianuacare.infrastructure.storage.database import DatabaseClient


class Reader:
    """Reads domain records through the configured ``DatabaseClient``."""

    def __init__(self, db_client: DatabaseClient, bucket_client: BucketClient | None = None) -> None:
        self._db = db_client
        self._bucket = bucket_client

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
