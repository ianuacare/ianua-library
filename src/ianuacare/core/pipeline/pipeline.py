"""Compatibility facade composing :class:`PipelineModel` and :class:`PipelineDatabase`.

Historical callers used a single :class:`Pipeline` for both inference and
storage flows. This class preserves that public API while delegating to the
two specialized pipelines, which can also be obtained via the ``model`` and
``database`` properties for direct use.
"""

from __future__ import annotations

import warnings
from typing import Any

from ianuacare.core.audit.service import AuditService
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline_database import PipelineDatabase
from ianuacare.core.pipeline.pipeline_model import PipelineModel
from ianuacare.core.pipeline.storage_parsers import (
    StorageInputParser,
    StorageOutputParser,
)
from ianuacare.core.pipeline.validator import BucketContentType, DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


class Pipeline:
    """Deprecated facade over :class:`PipelineModel` + :class:`PipelineDatabase`.

    .. deprecated::
        Construct :class:`PipelineModel` and :class:`PipelineDatabase` directly,
        or read them off :class:`ianuacare.presets.IanuacareStack`
        (``stack.pipeline_model`` / ``stack.pipeline_database``). The facade is
        kept for backward compatibility and emits a :class:`DeprecationWarning`.
    """

    def __init__(
        self,
        data_manager: DataManager,
        validator: DataValidator,
        writer: Writer,
        reader: Reader,
        orchestrator: Orchestrator,
        audit_service: AuditService,
        *,
        storage_input_parser: StorageInputParser | None = None,
        storage_output_parser: StorageOutputParser | None = None,
        _suppress_deprecation: bool = False,
    ) -> None:
        if not _suppress_deprecation:
            warnings.warn(
                "Pipeline is deprecated; use PipelineModel + PipelineDatabase "
                "(e.g. stack.pipeline_model / stack.pipeline_database).",
                DeprecationWarning,
                stacklevel=2,
            )
        self._model = PipelineModel(
            data_manager=data_manager,
            validator=validator,
            writer=writer,
            orchestrator=orchestrator,
            audit_service=audit_service,
        )
        self._database = PipelineDatabase(
            data_manager=data_manager,
            validator=validator,
            writer=writer,
            reader=reader,
            audit_service=audit_service,
            input_parser=storage_input_parser,
            output_parser=storage_output_parser,
            embed_text_fn=orchestrator.embed_text,
        )

    @property
    def model(self) -> PipelineModel:
        """The inference pipeline."""
        return self._model

    @property
    def database(self) -> PipelineDatabase:
        """The storage pipeline (DB, vector, bucket)."""
        return self._database

    def run(self, input_data: Any, context: RequestContext) -> DataPacket:
        """Backward-compatible alias for ``run_model``."""
        return self._model.run_model(input_data, context)

    def run_model(self, input_data: Any, context: RequestContext) -> DataPacket:
        """Execute the model pipeline for ``input_data``."""
        return self._model.run_model(input_data, context)

    def run_crud(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Execute CRUD flow with either writer (write ops) or reader (read ops)."""
        return self._database.run_crud(operation, input_data, context)

    def run_vector(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Execute vector-store flow (``upsert`` / ``search`` / ``delete`` / ``scroll``)."""
        return self._database.run_vector(operation, input_data, context)

    def run_bucket(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
        *,
        content_type: BucketContentType,
        bucket_name: str | None = None,
    ) -> DataPacket:
        """Upload or retrieve bucket-backed artefacts (audio or text files)."""
        return self._database.run_bucket(
            operation,
            input_data,
            context,
            content_type=content_type,
            bucket_name=bucket_name,
        )

    def run_audio(
        self,
        operation: str,
        input_data: Any,
        context: RequestContext,
    ) -> DataPacket:
        """Backward-compatible alias for :meth:`run_bucket` with ``content_type='audio'``."""
        return self._database.run_bucket(
            operation,
            input_data,
            context,
            content_type="audio",
        )
