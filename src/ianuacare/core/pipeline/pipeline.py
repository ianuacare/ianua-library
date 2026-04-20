"""End-to-end pipeline orchestration."""

from __future__ import annotations

from typing import Any

from ianuacare.core.audit.service import AuditService
from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class Pipeline:
    """Runs model and CRUD flows over a shared collect/validate entrypoint."""

    def __init__(
        self,
        data_manager: DataManager,
        validator: DataValidator,
        writer: Writer,
        reader: Reader,
        orchestrator: Orchestrator,
        audit_service: AuditService,
    ) -> None:
        self._data_manager = data_manager
        self._validator = validator
        self._writer = writer
        self._reader = reader
        self._orchestrator = orchestrator
        self._audit = audit_service

    def run(self, input_data: Any, context: RequestContext) -> DataPacket:
        """Backward-compatible alias for ``run_model``."""
        return self.run_model(input_data, context)

    def run_model(self, input_data: Any, context: RequestContext) -> DataPacket:
        """Execute the model pipeline for ``input_data``."""
        packet = self._data_manager.collect(input_data, context)
        self._audit.log_event(
            "pipeline_started",
            context,
            {"stage": "collect"},
        )
        self._validator.validate(packet)
        self._writer.write_raw(packet, context)
        self._orchestrator.execute(packet, context)
        self._audit.log_event(
            "orchestration_completed",
            context,
            {"stage": "orchestrate"},
        )
        self._writer.write_processed(packet, context)
        self._writer.write_result(packet, context)
        self._audit.log_event(
            "pipeline_completed",
            context,
            {"stage": "complete"},
        )
        return packet

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
        """Execute vector-store flow (``upsert`` / ``search`` / ``delete``).

        Mirrors :meth:`run_crud` but targets the injected
        :class:`VectorDatabaseClient`. For ``search`` the caller may supply
        either ``vector`` (a pre-computed embedding) or ``prompt`` (a string
        that will be embedded on-the-fly via the ``text_embedder`` model).
        """
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
                vector = self._orchestrator.embed_text(prompt, context)
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
        else:
            raise ValidationError(f"Unsupported vector operation: {operation}")

        self._audit.log_event(
            "pipeline_vector_completed",
            context,
            {"operation": operation},
        )
        return packet

    def run_audio(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Execute audio upload/retrieval flow with DB + S3 references."""
        packet = self._data_manager.collect(input_data, context)
        self._audit.log_event(
            "pipeline_audio_started",
            context,
            {"operation": operation},
        )
        self._validator.validate(packet)
        payload = self._validator.validate_audio_payload(packet.validated_data, operation=operation)

        if operation == "prepare_upload":
            collection = self._require_text(payload.get("collection"), field="collection")
            packet.processed_data = self._writer.write_audio_upload_reference(
                collection=collection,
                payload=payload,
                context=context,
            )
        elif operation == "upload_direct":
            collection = self._require_text(payload.get("collection"), field="collection")
            packet.processed_data = self._writer.write_audio_direct_upload(
                collection=collection,
                payload=payload,
                context=context,
            )
        elif operation == "retrieve":
            collection = self._require_text(payload.get("collection"), field="collection")
            lookup_field = self._require_text(payload.get("lookup_field"), field="lookup_field")
            lookup_value = payload.get("lookup_value")
            packet.processed_data = self._reader.read_audio(
                collection=collection,
                lookup_field=lookup_field,
                lookup_value=lookup_value,
                context=context,
            )
        else:
            raise ValidationError(f"Unsupported audio operation: {operation}")

        self._audit.log_event(
            "pipeline_audio_completed",
            context,
            {"operation": operation},
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
