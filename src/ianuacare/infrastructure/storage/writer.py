"""Persist pipeline artifacts to database and object storage."""

from __future__ import annotations

import json
from typing import Any

from ianuacare.core.exceptions.errors import StorageError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.infrastructure.encryption import EncryptionService
from ianuacare.infrastructure.storage.bucket import BucketClient
from ianuacare.infrastructure.storage.database import DatabaseClient


class Writer:
    """Writes raw, processed, and result payloads; never logs health data in messages."""

    COL_RAW = "raw_records"
    COL_PROCESSED = "processed_records"
    COL_RESULTS = "inference_results"
    COL_LOGS = "application_logs"

    def __init__(
        self,
        db_client: DatabaseClient,
        bucket_client: BucketClient,
        encryption: EncryptionService | None = None,
    ) -> None:
        self._db = db_client
        self._bucket = bucket_client
        self._encryption = encryption

    def write_raw(self, packet: DataPacket, context: RequestContext) -> dict[str, Any]:
        """Persist raw payload metadata and optional blob."""
        try:
            key = self._blob_key(context, "raw", packet.metadata)
            blob_ref = self._bucket.upload(key, self._prepare_blob(packet.raw_data))
            record = {
                "user_id": context.user.user_id,
                "product": context.product,
                "blob_key": key,
                "blob": blob_ref,
            }
            return self._db.write(self.COL_RAW, record)
        except Exception as exc:
            raise StorageError("Failed to write raw data") from exc

    def write_processed(self, packet: DataPacket, context: RequestContext) -> dict[str, Any]:
        """Persist processed intermediate data."""
        try:
            key = self._blob_key(context, "processed", packet.metadata)
            blob_ref = self._bucket.upload(key, self._prepare_blob(packet.processed_data))
            record = {
                "user_id": context.user.user_id,
                "product": context.product,
                "blob_key": key,
                "blob": blob_ref,
            }
            return self._db.write(self.COL_PROCESSED, record)
        except Exception as exc:
            raise StorageError("Failed to write processed data") from exc

    def write_result(self, packet: DataPacket, context: RequestContext) -> dict[str, Any]:
        """Persist inference result."""
        try:
            key = self._blob_key(context, "result", packet.metadata)
            blob_ref = self._bucket.upload(key, self._prepare_blob(packet.inference_result))
            record = {
                "user_id": context.user.user_id,
                "product": context.product,
                "blob_key": key,
                "blob": blob_ref,
            }
            return self._db.write(self.COL_RESULTS, record)
        except Exception as exc:
            raise StorageError("Failed to write inference result") from exc

    def write_log(self, message: str, context: RequestContext) -> dict[str, Any]:
        """Persist a non-sensitive log line (no PHI/PII in ``message``)."""
        try:
            record = {
                "user_id": context.user.user_id,
                "product": context.product,
                "message": message,
            }
            return self._db.write(self.COL_LOGS, record)
        except Exception as exc:
            raise StorageError("Failed to write log") from exc

    def write_create(
        self,
        collection: str,
        payload: dict[str, Any],
        context: RequestContext,
    ) -> dict[str, Any]:
        """Create a CRUD record in ``collection``."""
        try:
            record = {
                **payload,
                "product": context.product,
                "user_id": context.user.user_id,
            }
            return self._db.create(collection, record)
        except Exception as exc:
            raise StorageError("Failed to create record") from exc

    def write_update(
        self,
        collection: str,
        *,
        lookup_field: str,
        lookup_value: Any,
        updates: dict[str, Any],
        context: RequestContext,
    ) -> dict[str, Any]:
        """Update CRUD records by lookup pair."""
        try:
            enriched_updates = {
                **updates,
                "product": context.product,
                "user_id": context.user.user_id,
            }
            return self._db.update(
                collection,
                key=lookup_field,
                value=lookup_value,
                updates=enriched_updates,
            )
        except Exception as exc:
            raise StorageError("Failed to update record") from exc

    def write_delete(
        self,
        collection: str,
        *,
        lookup_field: str,
        lookup_value: Any,
        context: RequestContext,
    ) -> dict[str, Any]:
        """Delete CRUD records by lookup pair."""
        try:
            _ = context  # currently unused; interface kept consistent with other methods
            return self._db.delete(
                collection,
                key=lookup_field,
                value=lookup_value,
            )
        except Exception as exc:
            raise StorageError("Failed to delete record") from exc

    @staticmethod
    def _blob_key(
        context: RequestContext,
        phase: str,
        packet_meta: dict[str, Any],
    ) -> str:
        """Build a storage key; uses only ids from metadata, not health content."""
        rid = packet_meta.get("request_id", "unknown")
        return f"{context.product}/{context.user.user_id}/{phase}/{rid}"

    def _prepare_blob(self, payload: Any) -> Any:
        if self._encryption is None:
            return payload
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
        return self._encryption.encrypt(raw)

