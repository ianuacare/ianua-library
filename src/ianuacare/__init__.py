"""Ianuacare: healthcare data pipeline and AI inference framework."""

from ianuacare.ai import AIProvider, BaseAIModel, NLPModel
from ianuacare.core.audit import AuditService
from ianuacare.core.auth import (
    AuthService,
    CognitoAccountService,
    CognitoLoginService,
    CognitoRegistrationService,
    UserRepository,
)
from ianuacare.core.config import ConfigService, EnvConfigService
from ianuacare.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    IanuacareError,
    InferenceError,
    OrchestrationError,
    StorageError,
    ValidationError,
)
from ianuacare.core.logging import StructuredLogger
from ianuacare.core.models import (
    DataPacket,
    LoginTokens,
    PasswordResetDelivery,
    RegistrationResult,
    RequestContext,
    User,
    UserProfile,
)
from ianuacare.core.orchestration import DataParser, Orchestrator
from ianuacare.core.pipeline import DataManager, DataValidator, Pipeline
from ianuacare.infrastructure import (
    CacheClient,
    EncryptionService,
    InMemoryCacheClient,
    NoOpEncryption,
)
from ianuacare.infrastructure.storage import (
    BucketClient,
    DatabaseClient,
    InMemoryBucketClient,
    InMemoryDatabaseClient,
    PostgresDatabaseClient,
    Reader,
    S3BucketClient,
    Writer,
)
from ianuacare.presets import IanuacareStack, create_stack

__version__ = "0.1.0"

__all__ = [
    "AIProvider",
    "AuditService",
    "AuthService",
    "AuthenticationError",
    "CognitoAccountService",
    "CognitoLoginService",
    "CognitoRegistrationService",
    "AuthorizationError",
    "BaseAIModel",
    "BucketClient",
    "CacheClient",
    "ConfigService",
    "EnvConfigService",
    "DataManager",
    "DataPacket",
    "DataParser",
    "DataValidator",
    "DatabaseClient",
    "IanuacareError",
    "InferenceError",
    "InMemoryBucketClient",
    "InMemoryCacheClient",
    "InMemoryDatabaseClient",
    "NLPModel",
    "OrchestrationError",
    "Orchestrator",
    "Pipeline",
    "PostgresDatabaseClient",
    "Reader",
    "RequestContext",
    "S3BucketClient",
    "StructuredLogger",
    "StorageError",
    "EncryptionService",
    "NoOpEncryption",
    "User",
    "UserRepository",
    "ValidationError",
    "Writer",
    "IanuacareStack",
    "create_stack",
    "LoginTokens",
    "PasswordResetDelivery",
    "RegistrationResult",
    "UserProfile",
]
