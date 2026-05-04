"""Storage pipeline: CRUD, vector, and bucket flows.

This pipeline owns persistence concerns over PostgreSQL, S3 buckets, and
Qdrant. It composes :class:`DataManager`, :class:`DataValidator`,
:class:`Writer`, :class:`Reader`, plus dedicated storage-side input/output
parsers (see :mod:`ianuacare.core.pipeline.storage_parsers`) which are
intentionally distinct from the model-oriented parsers wrapped by
:class:`Orchestrator`.

For vector search by ``prompt``, an ``embed_text_fn`` callable is injected so
this pipeline does not depend on the full :class:`Orchestrator` type.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ianuacare.core.audit.service import AuditService
from ianuacare.core.exceptions.errors import OrchestrationError, ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.storage_parsers import (
    PassthroughStorageInputParser,
    PassthroughStorageOutputParser,
    StorageInputParser,
    StorageOutputParser,
)
from ianuacare.core.pipeline.validator import BucketContentType, DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer

EmbedTextFn = Callable[[str, RequestContext], list[float]]


class PipelineDatabase:
    """Runs CRUD, vector, and bucket I/O flows over Postgres, S3, and Qdrant."""

    def __init__(
        self,
        data_manager: DataManager,
        validator: DataValidator,
        writer: Writer,
        reader: Reader,
        audit_service: AuditService,
        *,
        input_parser: StorageInputParser | None = None,
        output_parser: StorageOutputParser | None = None,
        embed_text_fn: EmbedTextFn | None = None,
    ) -> None:
        self._data_manager = data_manager
        self._validator = validator
        self._writer = writer
        self._reader = reader
        self._audit = audit_service
        self._input_parser = input_parser or PassthroughStorageInputParser()
        self._output_parser = output_parser or PassthroughStorageOutputParser()
        self._embed_text_fn = embed_text_fn

    def run_crud(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Execute CRUD flow with either writer (write ops) or reader (read ops)."""
        packet = self._data_manager.collect(input_data, context)
        self._audit.log_event(
            "pipeline_crud_started",
            context,
            {"operation": operation},
        )
        self._validator.validate(packet)
        payload = self._require_mapping(packet.validated_data)
        collection = payload.get("collection")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required for CRUD operations")

        is_write = operation in {"create", "update", "delete"}
        if is_write:
            self._input_parser.prepare_for_persist(
                packet, channel="crud", operation=operation, context=context
            )

        if operation == "create":
            record = self._require_mapping(payload.get("record"), field="record")
            packet.processed_data = self._writer.write_create(collection, record, context)
        elif operation == "update":
            lookup_field = self._require_text(payload.get("lookup_field"), field="lookup_field")
            lookup_value = payload.get("lookup_value")
            updates = self._require_mapping(payload.get("updates"), field="updates")
            packet.processed_data = self._writer.write_update(
                collection,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                updates=updates,
                context=context,
            )
        elif operation == "delete":
            lookup_field = self._require_text(payload.get("lookup_field"), field="lookup_field")
            lookup_value = payload.get("lookup_value")
            packet.processed_data = self._writer.write_delete(
                collection,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                context=context,
            )
        elif operation == "read_one":
            lookup_field = self._require_text(payload.get("lookup_field"), field="lookup_field")
            lookup_value = payload.get("lookup_value")
            packet.processed_data = self._reader.read_one(
                collection,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                context=context,
            )
        elif operation == "read_many":
            filters = payload.get("filters")
            if filters is not None and not isinstance(filters, dict):
                raise ValidationError("filters must be a mapping when provided")
            packet.processed_data = self._reader.read_many(
                collection,
                filters=filters,
                context=context,
            )
        else:
            raise ValidationError(f"Unsupported CRUD operation: {operation}")

        if not is_write:
            self._output_parser.after_read(
                packet, channel="crud", operation=operation, context=context
            )

        self._audit.log_event(
            "pipeline_crud_completed",
            context,
            {"operation": operation},
        )
        return packet

    def run_vector(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Execute vector-store flow (``upsert`` / ``search`` / ``delete`` / ``scroll``)."""
        packet = self._data_manager.collect(input_data, context)
        self._audit.log_event(
            "pipeline_vector_started",
            context,
            {"operation": operation},
        )
        self._validator.validate(packet)
        payload = self._validator.validate_vector_payload(
            packet.validated_data, operation=operation
        )
        collection = self._require_text(payload.get("collection"), field="collection")

        is_write = operation in {"upsert", "delete"}
        if is_write:
            self._input_parser.prepare_for_persist(
                packet, channel="vector", operation=operation, context=context
            )

        if operation == "upsert":
            artefatti = payload.get("artefatti") or []
            vector_field = self._require_text(
                payload.get("vector_field"), field="vector_field"
            )
            packet.processed_data = self._writer.write_vector_upsert(
                collection,
                artefatti,
                vector_field=vector_field,
                context=context,
            )
        elif operation == "search":
            vector = payload.get("vector")
            if not isinstance(vector, list) or not vector:
                prompt = self._require_text(payload.get("prompt"), field="prompt")
                if self._embed_text_fn is None:
                    raise OrchestrationError(
                        "embed_text_fn is not configured; cannot embed prompt for vector search"
                    )
                vector = self._embed_text_fn(prompt, context)
            filters = payload.get("filters")
            if not isinstance(filters, dict):
                raise ValidationError("filters must be a mapping")
            top_k = int(payload.get("top_k", 10))
            score_threshold = payload.get("score_threshold")
            packet.processed_data = self._reader.read_vector_search(
                collection,
                vector=vector,
                top_k=top_k,
                filters=filters,
                score_threshold=score_threshold,
                context=context,
            )
        elif operation == "delete":
            ids = payload.get("ids")
            filters = payload.get("filters")
            if filters is not None and not isinstance(filters, dict):
                raise ValidationError("filters must be a mapping when provided")
            packet.processed_data = self._writer.write_vector_delete(
                collection,
                ids=ids,
                filters=filters,
                context=context,
            )
        elif operation == "scroll":
            filters = payload.get("filters")
            if filters is not None and not isinstance(filters, dict):
                raise ValidationError("filters must be a mapping when provided")
            batch_size = int(payload.get("batch_size", 256))
            with_vectors = bool(payload.get("with_vectors", False))
            with_payload = bool(payload.get("with_payload", True))
            packet.processed_data = self._reader.read_vector_scroll(
                collection,
                filters=filters,
                batch_size=batch_size,
                with_vectors=with_vectors,
                with_payload=with_payload,
                context=context,
            )
        else:
            raise ValidationError(f"Unsupported vector operation: {operation}")

        if not is_write:
            self._output_parser.after_read(
                packet, channel="vector", operation=operation, context=context
            )

        self._audit.log_event(
            "pipeline_vector_completed",
            context,
            {"operation": operation},
        )
        return packet

    def run_bucket(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
        *,
        content_type: BucketContentType,
        bucket_name: str | None = None,
    ) -> DataPacket:
        """Upload or retrieve objects from object storage with DB metadata.

        ``content_type`` selects validation rules and object-key layout (``audio``
        vs ``text`` under the configured bucket). ``bucket_name`` is reserved for
        multi-bucket routing in application wiring; when set, it is stored on
        ``packet.metadata[\"bucket_name\"]`` for downstream adapters.

        Operations: ``prepare_upload``, ``upload_direct``, ``retrieve``.
        """
        packet = self._data_manager.collect(input_data, context)
        if bucket_name:
            packet.metadata["bucket_name"] = bucket_name

        details: dict[str, str] = {
            "operation": operation,
            "content_type": content_type,
        }
        if bucket_name:
            details["bucket_name"] = bucket_name

        self._audit.log_event(
            "pipeline_bucket_started",
            context,
            details,
        )
        self._validator.validate(packet)
        payload = self._validator.validate_bucket_payload(
            packet.validated_data,
            content_type=content_type,
            operation=operation,
        )

        is_write = operation in {"prepare_upload", "upload_direct"}
        if is_write:
            self._input_parser.prepare_for_persist(
                packet, channel="bucket", operation=operation, context=context
            )

        if operation == "prepare_upload":
            collection = self._require_text(payload.get("collection"), field="collection")
            packet.processed_data = self._writer.write_bucket_upload_reference(
                collection=collection,
                payload=payload,
                context=context,
                content_type=content_type,
            )
        elif operation == "upload_direct":
            collection = self._require_text(payload.get("collection"), field="collection")
            packet.processed_data = self._writer.write_bucket_direct_upload(
                collection=collection,
                payload=payload,
                context=context,
                content_type=content_type,
            )
        elif operation == "retrieve":
            collection = self._require_text(payload.get("collection"), field="collection")
            lookup_field = self._require_text(payload.get("lookup_field"), field="lookup_field")
            lookup_value = payload.get("lookup_value")
            packet.processed_data = self._reader.read_bucket(
                collection=collection,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                context=context,
            )
        else:
            raise ValidationError(f"Unsupported bucket operation: {operation}")

        if not is_write:
            self._output_parser.after_read(
                packet, channel="bucket", operation=operation, context=context
            )

        self._audit.log_event(
            "pipeline_bucket_completed",
            context,
            details,
        )
        return packet

    @staticmethod
    def _require_mapping(value: Any, *, field: str = "payload") -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError(f"{field} must be a mapping")
        return value

    @staticmethod
    def _require_text(value: Any, *, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{field} is required")
        return value
