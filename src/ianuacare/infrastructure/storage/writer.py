"""Persist pipeline artifacts to database and object storage."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ianuacare.core.exceptions.errors import StorageError, ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.infrastructure.encryption import EncryptionService
from ianuacare.infrastructure.storage.bucket import BucketClient
from ianuacare.infrastructure.storage.database import DatabaseClient
from ianuacare.infrastructure.storage.vector import VectorDatabaseClient


_VECTOR_FIELD_MAP: dict[str, tuple[str, str]] = {
    "text": ("text", "text_vect"),
    "sentence": ("sentence", "sentence_vect"),
    "words": ("words", "words_vect"),
}


class Writer:
    """Writes raw, processed, and result payloads; never logs health data in messages."""

    COL_RAW = "raw_records"
    COL_PROCESSED = "processed_records"
    COL_RESULTS = "inference_results"
    COL_LOGS = "application_logs"
    COL_AUDIO = "audio_records"

    def __init__(
        self,
        db_client: DatabaseClient,
        bucket_client: BucketClient,
        encryption: EncryptionService | None = None,
        vector_client: VectorDatabaseClient | None = None,
    ) -> None:
        self._db = db_client
        self._bucket = bucket_client
        self._encryption = encryption
        self._vector = vector_client

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

    def write_audio_upload_reference(
        self,
        *,
        collection: str,
        payload: dict[str, Any],
        context: RequestContext,
    ) -> dict[str, Any]:
        """Persist audio metadata and return a presigned upload URL."""
        try:
            filename = str(payload.get("filename") or "").strip()
            if not filename:
                raise ValueError("filename is required")
            ext = Path(filename).suffix.lower()
            if ext not in {".wav", ".mp3"}:
                raise ValueError("filename extension must be .wav or .mp3")

            audio_id = str(payload.get("audio_id") or uuid.uuid4().hex)
            request_id = str(payload.get("request_id") or payload.get("meta_request_id") or "")
            seed = request_id if request_id else audio_id
            object_key = f"{context.product}/{context.user.user_id}/audio/{seed}{ext}"

            mime_type = str(payload.get("mime_type") or self._mime_from_ext(ext))
            size_bytes = payload.get("size_bytes")
            upload_url = self._generate_upload_url(
                object_key=object_key,
                mime_type=mime_type,
                expires_in=int(payload.get("upload_url_expires_in") or 900),
            )
            record = {
                "audio_id": audio_id,
                "user_id": context.user.user_id,
                "product": context.product,
                "status": "pending_upload",
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "bucket": self._bucket_name(),
                "object_key": object_key,
                "request_id": request_id or payload.get("meta_request_id"),
            }
            self._db.write(collection or self.COL_AUDIO, record)
            return {
                "audio_id": audio_id,
                "bucket": record["bucket"],
                "object_key": object_key,
                "mime_type": mime_type,
                "status": record["status"],
                "upload_url": upload_url,
                "upload_url_expires_in": int(payload.get("upload_url_expires_in") or 900),
            }
        except Exception as exc:
            raise StorageError("Failed to prepare audio upload") from exc

    def write_audio_direct_upload(
        self,
        *,
        collection: str,
        payload: dict[str, Any],
        context: RequestContext,
    ) -> dict[str, Any]:
        """Upload audio bytes to object storage and persist metadata."""
        try:
            filename = str(payload.get("filename") or "").strip()
            if not filename:
                raise ValueError("filename is required")
            ext = Path(filename).suffix.lower()
            if ext not in {".wav", ".mp3"}:
                raise ValueError("filename extension must be .wav or .mp3")

            content = payload.get("content")
            if isinstance(content, str):
                body = content.encode()
            elif isinstance(content, (bytes, bytearray)):
                body = bytes(content)
            else:
                raise ValueError("content is required")
            if not body:
                raise ValueError("content is empty")

            audio_id = str(payload.get("audio_id") or uuid.uuid4().hex)
            request_id = str(payload.get("request_id") or payload.get("meta_request_id") or "")
            seed = request_id if request_id else audio_id
            object_key = f"{context.product}/{context.user.user_id}/audio/{seed}{ext}"
            mime_type = str(payload.get("mime_type") or self._mime_from_ext(ext))

            blob_ref = self._bucket.upload(object_key, body)
            record = {
                "audio_id": audio_id,
                "user_id": context.user.user_id,
                "product": context.product,
                "status": "uploaded",
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(body),
                "bucket": self._bucket_name(),
                "object_key": object_key,
                "request_id": request_id or payload.get("meta_request_id"),
                "blob": blob_ref,
            }
            self._db.write(collection or self.COL_AUDIO, record)
            return {
                "audio_id": audio_id,
                "bucket": record["bucket"],
                "object_key": object_key,
                "mime_type": mime_type,
                "size_bytes": record["size_bytes"],
                "status": record["status"],
            }
        except Exception as exc:
            raise StorageError("Failed to upload audio directly") from exc

    def write_vector_upsert(
        self,
        collection: str,
        artefatti: list[dict[str, Any]],
        *,
        vector_field: str,
        context: RequestContext,
    ) -> dict[str, Any]:
        """Upsert one point per element of ``vector_field`` across all artefacts.

        ``vector_field`` selects the level to persist: ``"text"`` produces
        one point per artefact (``index=0``), ``"sentence"`` and ``"words"``
        produce one point per list element. Each point has a stable id of
        the form ``{id_artefatto_trascrizione}:{level}:{index}`` and a
        payload with ``user_id``, ``product``, ``level``, ``index`` and
        ``source_text``.
        """
        if self._vector is None:
            raise StorageError("vector_client is not configured on Writer")
        if vector_field not in _VECTOR_FIELD_MAP:
            raise ValidationError(
                f"vector_field must be one of {sorted(_VECTOR_FIELD_MAP)}"
            )
        if not isinstance(artefatti, list):
            raise ValidationError("artefatti must be a list")

        text_key, vector_key = _VECTOR_FIELD_MAP[vector_field]
        points = self._build_points(
            artefatti=artefatti,
            vector_field=vector_field,
            text_key=text_key,
            vector_key=vector_key,
            context=context,
        )
        try:
            return self._vector.upsert(collection, points)
        except Exception as exc:
            raise StorageError("Failed to upsert vector points") from exc

    def write_vector_delete(
        self,
        collection: str,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, Any] | None = None,
        context: RequestContext,
    ) -> dict[str, Any]:
        """Delete vector points by explicit ``ids`` or by exact-match ``filters``."""
        if self._vector is None:
            raise StorageError("vector_client is not configured on Writer")
        _ = context  # interface parity with other write methods
        if ids is None and not filters:
            raise ValidationError("vector delete requires 'ids' or 'filters'")
        try:
            return self._vector.delete(collection, ids=ids, filters=filters)
        except Exception as exc:
            raise StorageError("Failed to delete vector points") from exc

    @staticmethod
    def _build_points(
        *,
        artefatti: list[dict[str, Any]],
        vector_field: str,
        text_key: str,
        vector_key: str,
        context: RequestContext,
    ) -> list[dict[str, Any]]:
        """Materialize Qdrant-style points for the selected level of each artefact."""
        points: list[dict[str, Any]] = []
        for artefact in artefatti:
            if not isinstance(artefact, dict):
                raise ValidationError("each artefact must be a mapping")
            artefact_id = artefact.get("id_artefatto_trascrizione")
            if not isinstance(artefact_id, str) or not artefact_id:
                raise ValidationError("artefact missing 'id_artefatto_trascrizione'")

            if vector_field == "text":
                vector = artefact.get(vector_key)
                text = artefact.get(text_key, "")
                if not isinstance(vector, list):
                    raise ValidationError(
                        f"artefact '{artefact_id}' missing '{vector_key}' list"
                    )
                points.append(
                    {
                        "id": f"{artefact_id}:{vector_field}:0",
                        "vector": list(vector),
                        "payload": {
                            "user_id": context.user.user_id,
                            "product": context.product,
                            "id_artefatto_trascrizione": artefact_id,
                            "level": vector_field,
                            "index": 0,
                            "source_text": text,
                        },
                    }
                )
                continue

            texts = artefact.get(text_key, [])
            vectors = artefact.get(vector_key, [])
            if not isinstance(texts, list) or not isinstance(vectors, list):
                raise ValidationError(
                    f"artefact '{artefact_id}' requires '{text_key}' and '{vector_key}' lists"
                )
            if len(texts) != len(vectors):
                raise ValidationError(
                    f"artefact '{artefact_id}' has mismatched '{text_key}'/'{vector_key}' lengths"
                )
            for index, (source_text, vector) in enumerate(zip(texts, vectors, strict=True)):
                if not isinstance(vector, list):
                    raise ValidationError(
                        f"artefact '{artefact_id}' vector at index {index} is not a list"
                    )
                points.append(
                    {
                        "id": f"{artefact_id}:{vector_field}:{index}",
                        "vector": list(vector),
                        "payload": {
                            "user_id": context.user.user_id,
                            "product": context.product,
                            "id_artefatto_trascrizione": artefact_id,
                            "level": vector_field,
                            "index": index,
                            "source_text": source_text,
                        },
                    }
                )
        return points

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

    def _generate_upload_url(self, *, object_key: str, mime_type: str, expires_in: int) -> str:
        generator = getattr(self._bucket, "generate_presigned_upload_url", None)
        if not callable(generator):
            raise StorageError("Bucket client does not support presigned upload URLs")
        return str(generator(object_key, mime_type=mime_type, expires_in=expires_in))

    def _bucket_name(self) -> str:
        name = getattr(self._bucket, "_bucket_name", None)
        return str(name) if isinstance(name, str) and name else "unknown"

    @staticmethod
    def _mime_from_ext(ext: str) -> str:
        return "audio/wav" if ext == ".wav" else "audio/mpeg"

