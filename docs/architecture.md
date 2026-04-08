# Architecture

## Design overview

Ianuacare now exposes two flows over the same `DataPacket` entrypoint:

- **Model flow**: `collect -> validate -> persist raw -> orchestrate (parse + model) -> persist processed -> persist result`
- **CRUD flow**: `collect -> validate -> writer (create/update/delete)` or `collect -> validate -> reader (read_one/read_many)`

Both flows produce audit events; CRUD outputs are written to `packet.processed_data`.

```mermaid
flowchart LR
    inputData[InputData] --> collectStep[DataManager.collect]
    collectStep --> validateStep[DataValidator.validate]

    validateStep -->|model| writeRaw[Writer.write_raw]
    writeRaw --> executeStep[Orchestrator.execute]
    executeStep --> writeProcessed[Writer.write_processed]
    writeProcessed --> writeResult[Writer.write_result]
    writeResult --> modelResult["DataPacket (inference_result)"]

    validateStep -->|crud_write| crudWrite[Writer.write_create_update_delete]
    crudWrite --> crudResult["DataPacket (processed_data)"]

    validateStep -->|crud_read| crudRead[Reader.read_one_many]
    crudRead --> crudResult

    subgraph audit [AuditService]
        logEvent[log_event]
    end

    collectStep -.-> logEvent
    executeStep -.-> logEvent
    writeResult -.-> logEvent
    crudWrite -.-> logEvent
    crudRead -.-> logEvent
```

## Layering (3 layers)

| Layer | Responsibility | Main modules |
|-------|----------------|--------------|
| **Core** | Domain models, business flow, errors, auth, orchestration and pipeline logic. | `ianuacare.core.models`, `ianuacare.core.pipeline`, `ianuacare.core.orchestration`, `ianuacare.core.auth`, `ianuacare.core.audit`, `ianuacare.core.config`, `ianuacare.core.logging`, `ianuacare.core.exceptions` |
| **AI** | AI abstractions and AI area packages. | `ianuacare.ai.base`, `ianuacare.ai.provider`, `ianuacare.ai.providers`, `ianuacare.ai.nlp`, `ianuacare.ai.cv`, `ianuacare.ai.tabular` |
| **Infrastructure** | External adapters and persistence implementations. | `ianuacare.infrastructure.storage`, `ianuacare.infrastructure.auth`, `ianuacare.infrastructure.cache`, `ianuacare.infrastructure.encryption` |

## Package structure

```text
src/ianuacare/
  core/
  ai/
    providers/
    nlp/
    cv/
    tabular/
  infrastructure/
    auth/
    cache/
    encryption/
    storage/
  presets/
```

## Relationships (from the class diagram)

- **Composition**: `Pipeline` holds `DataManager`, `DataValidator`, `Writer`, `Reader`, `Orchestrator`, `AuditService`. `Writer` holds `DatabaseClient`, `BucketClient`, optional `EncryptionService`. `Reader` holds `DatabaseClient`. `Orchestrator` holds `DataParser`, a `dict[str, BaseAIModel]`, optional `CacheClient`. `AuthService` holds `UserRepository`. `CognitoLoginService` composes `CognitoPasswordAuthenticator` (infrastructure) to perform `USER_PASSWORD_AUTH`, then callers typically pass the access token to `AuthService` with `CognitoUserRepository`. `CognitoRegistrationService` composes `CognitoRegistrationClient` for `SignUp` / `ConfirmSignUp`. `CognitoAccountService` composes `CognitoAccountClient` for password recovery, `GlobalSignOut`, `ChangePassword`, and `UpdateUserAttributes`. `NLPModel` holds `AIProvider`.
- **Dependency**: most services accept `DataPacket` and `RequestContext` per call (no long-lived coupling).
- **Inheritance**: `NLPModel` extends `BaseAIModel`; concrete errors extend `IanuacareError`.

## Healthcare considerations

- **No PHI in audit `details`**: pass only structured identifiers; never patient names, diagnoses, or free text in audit records used for operations.
- **Encryption**: this library does not encrypt payloads; use application-layer or database encryption for regulated data.
- **Authorization**: `AuthService.authorize()` is explicit; wire it in HTTP/API layers before calling `Pipeline.run_model()` or `Pipeline.run_crud()`.

## In-memory implementations

`InMemoryDatabaseClient` and `InMemoryBucketClient` are provided for **tests and local development**. Production code should use adapters that talk to PostgreSQL, object storage, etc., implementing the same protocols.

`PostgresDatabaseClient` persists CRUD records using relational columns and safe SQL composition (`psycopg.sql.Identifier` for table/column names), while allowing JSONB only for variable-shaped values when needed.
