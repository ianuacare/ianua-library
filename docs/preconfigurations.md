# Preconfigurations

Ianuacare now ships production-oriented adapters and a vendor-agnostic stack factory.

## Available adapters

### :material-shield-account: Auth

- :fontawesome-brands-aws: `CognitoUserRepository` (`ianuacare.infrastructure.auth`) — resolves a principal from a **Cognito access token** (and JWT claim attributes).
- :fontawesome-brands-aws: `CognitoLoginService` (`ianuacare.core.auth`, re-exported from `ianuacare`) — **password login** via `USER_PASSWORD_AUTH`, returns `LoginTokens`.
- :fontawesome-brands-aws: `CognitoPasswordAuthenticator` (`ianuacare.infrastructure.auth`) — low-level `InitiateAuth` wrapper (used by `CognitoLoginService`).
- :fontawesome-brands-aws: `CognitoRegistrationService` (`ianuacare.core.auth`) — self-service `SignUp` / `ConfirmSignUp`.
- :fontawesome-brands-aws: `CognitoRegistrationClient` (`ianuacare.infrastructure.auth`) — low-level registration wrapper.
- :fontawesome-brands-aws: `CognitoAccountService` (`ianuacare.core.auth`) — forgot/reset password, global sign-out, change password, update attributes.
- :fontawesome-brands-aws: `CognitoAccountClient` (`ianuacare.infrastructure.auth`) — low-level account/session calls.

All require the **`aws`** extra (`pip install "ianuacare[aws]"` or equivalent): `boto3`, and `python-jose` for JWT claim reads in `CognitoUserRepository`.

### :material-database: Storage

- :simple-postgresql: `PostgresDatabaseClient` (`ianuacare.infrastructure.storage`) for relational persistence with dynamic columns (safe identifiers via `psycopg.sql`).
- :fontawesome-brands-aws: `S3BucketClient` (`ianuacare.infrastructure.storage`) for blob/object storage.
- `Reader` and `Writer` (`ianuacare.infrastructure.storage`) for CRUD reads/writes and pipeline artifact persistence over `DatabaseClient`.

### :material-robot-outline: AI provider

- :material-brain: `TogetherAIProvider` (`ianuacare.ai.providers`) for Together chat inference.

### :material-lightning-bolt-circle: Cache and encryption

- `CacheClient` + `InMemoryCacheClient` (`ianuacare.infrastructure.cache`)
- :simple-redis: `RedisCacheClient` (`ianuacare.infrastructure.cache.redis`)
- `EncryptionService` + `NoOpEncryption` (`ianuacare.infrastructure.encryption`)
- :fontawesome-brands-aws: `KMSEncryptionService` (`ianuacare.infrastructure.encryption.kms`)

### :material-cog-outline: Configuration and logging

- `EnvConfigService` (`ianuacare.core.config`) reads `IANUA_*` environment variables.
- :material-math-log: `StructuredLogger` (`ianuacare.core.logging`) emits JSON logs with context fields.

## Generic factory

Use `create_stack()` to wire the framework without vendor lock-in:

```python
from ianuacare import (
    InMemoryBucketClient,
    InMemoryDatabaseClient,
    NLPModel,
    AIProvider,
    UserRepository,
    create_stack,
)

provider = AIProvider()
model = NLPModel(provider, "clinical")

stack = create_stack(
    auth_repository=UserRepository(),
    database=InMemoryDatabaseClient(),
    bucket=InMemoryBucketClient(),
    models={"nlp": model},
    default_model_key="nlp",
)

# stack.pipeline, stack.auth_service, stack.writer, stack.orchestrator
```

For production, pass concrete adapters (Cognito/Postgres/S3/Redis/KMS) instead of in-memory ones.
