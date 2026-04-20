"""Storage clients and writer."""

from ianuacare.infrastructure.storage.bucket import BucketClient, InMemoryBucketClient
from ianuacare.infrastructure.storage.database import (
    DatabaseClient,
    InMemoryDatabaseClient,
)
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.vector import (
    InMemoryVectorDatabaseClient,
    VectorDatabaseClient,
)
from ianuacare.infrastructure.storage.writer import Writer

try:  # Optional dependency: psycopg
    from ianuacare.infrastructure.storage.postgres import PostgresDatabaseClient
except Exception:  # pragma: no cover - import-time optional dependency handling
    PostgresDatabaseClient = None  # type: ignore[assignment]

try:  # Optional dependency: boto3
    from ianuacare.infrastructure.storage.s3 import S3BucketClient
except Exception:  # pragma: no cover - import-time optional dependency handling
    S3BucketClient = None  # type: ignore[assignment]

try:  # Optional dependency: qdrant-client
    from ianuacare.infrastructure.storage.qdrant import QdrantDatabaseClient
except Exception:  # pragma: no cover - import-time optional dependency handling
    QdrantDatabaseClient = None  # type: ignore[assignment]

__all__ = [
    "BucketClient",
    "DatabaseClient",
    "InMemoryBucketClient",
    "InMemoryDatabaseClient",
    "InMemoryVectorDatabaseClient",
    "PostgresDatabaseClient",
    "QdrantDatabaseClient",
    "Reader",
    "S3BucketClient",
    "VectorDatabaseClient",
    "Writer",
]

