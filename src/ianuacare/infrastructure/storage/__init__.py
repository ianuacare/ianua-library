"""Storage clients and writer."""

from ianuacare.infrastructure.storage.bucket import BucketClient, InMemoryBucketClient
from ianuacare.infrastructure.storage.database import (
    DatabaseClient,
    InMemoryDatabaseClient,
)
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer

try:  # Optional dependency: psycopg
    from ianuacare.infrastructure.storage.postgres import PostgresDatabaseClient
except Exception:  # pragma: no cover - import-time optional dependency handling
    PostgresDatabaseClient = None  # type: ignore[assignment]

try:  # Optional dependency: boto3
    from ianuacare.infrastructure.storage.s3 import S3BucketClient
except Exception:  # pragma: no cover - import-time optional dependency handling
    S3BucketClient = None  # type: ignore[assignment]

__all__ = [
    "BucketClient",
    "DatabaseClient",
    "InMemoryBucketClient",
    "InMemoryDatabaseClient",
    "PostgresDatabaseClient",
    "Reader",
    "S3BucketClient",
    "Writer",
]

