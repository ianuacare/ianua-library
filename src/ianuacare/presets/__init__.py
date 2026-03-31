"""Convenience factory for wiring a complete Ianuacare stack."""

from __future__ import annotations

from dataclasses import dataclass

from ianuacare.ai.base import BaseAIModel
from ianuacare.core.audit import AuditService
from ianuacare.core.auth import AuthService
from ianuacare.core.config.env import EnvConfigService
from ianuacare.core.logging import StructuredLogger
from ianuacare.core.orchestration import DataParser, Orchestrator
from ianuacare.core.pipeline import DataManager, DataValidator, Pipeline
from ianuacare.infrastructure.cache import CacheClient
from ianuacare.infrastructure.encryption import EncryptionService
from ianuacare.infrastructure.storage import BucketClient, DatabaseClient, Reader, Writer


@dataclass(slots=True)
class IanuacareStack:
    """Container with pre-wired framework services."""

    auth_service: AuthService
    pipeline: Pipeline
    writer: Writer
    orchestrator: Orchestrator
    logger: StructuredLogger
    config: EnvConfigService


def create_stack(
    *,
    auth_repository: object,
    database: DatabaseClient,
    bucket: BucketClient,
    models: dict[str, BaseAIModel],
    default_model_key: str | None = None,
    cache: CacheClient | None = None,
    cache_ttl_seconds: int | None = 300,
    encryption: EncryptionService | None = None,
    config: EnvConfigService | None = None,
    logger: StructuredLogger | None = None,
) -> IanuacareStack:
    """Create all core services from injected adapters."""
    auth_service = AuthService(user_repository=auth_repository)  # type: ignore[arg-type]
    writer = Writer(database, bucket, encryption=encryption)
    orchestrator = Orchestrator(
        parser=DataParser(),
        models=models,
        default_model_key=default_model_key,
        cache=cache,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    pipeline = Pipeline(
        data_manager=DataManager(),
        validator=DataValidator(),
        writer=writer,
        reader=Reader(database),
        orchestrator=orchestrator,
        audit_service=AuditService(database),
    )
    return IanuacareStack(
        auth_service=auth_service,
        pipeline=pipeline,
        writer=writer,
        orchestrator=orchestrator,
        logger=logger or StructuredLogger(),
        config=config or EnvConfigService(),
    )


__all__ = ["IanuacareStack", "create_stack"]
