"""Inference pipeline: collect, validate, orchestrate model execution."""

from __future__ import annotations

from typing import Any

from ianuacare.core.audit.service import AuditService
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.writer import Writer


class PipelineModel:
    """Runs the AI inference flow.

    Sequence: ``collect -> validate -> write_raw -> orchestrate -> write_processed
    -> write_result``. The model artifacts persistence (raw/processed/result) is
    intrinsic to a model run and lives here, distinct from generic CRUD/bucket
    storage handled by :class:`PipelineDatabase`.
    """

    def __init__(
        self,
        data_manager: DataManager,
        validator: DataValidator,
        writer: Writer,
        orchestrator: Orchestrator,
        audit_service: AuditService,
    ) -> None:
        self._data_manager = data_manager
        self._validator = validator
        self._writer = writer
        self._orchestrator = orchestrator
        self._audit = audit_service

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
