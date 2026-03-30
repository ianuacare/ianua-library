# API reference

Public symbols are re-exported from `ianuacare` (`from ianuacare import ...`).

## Domain models

Module path: `ianuacare.core.models`

### `User`

- `user_id: str`
- `role: str`
- `permissions: list[str]`

### `RequestContext`

- `user: User`
- `product: str`
- `metadata: dict` — use for **non-PHI** routing keys (e.g. `model_key`).

### `LoginTokens`

Module path: `ianuacare.core.models.login_tokens`

- `access_token: str`, `id_token: str`, `refresh_token: str`
- `token_type: str` (default `"Bearer"`)
- `expires_in: int | None` — seconds, when provided by the IdP

### `DataPacket`

Mutable pipeline state:

- `raw_data`, `parsed_data`, `validated_data`, `processed_data`, `inference_result`
- `metadata: dict` — includes `request_id`, `product`, `user_id` after `DataManager.collect()`.

## Exceptions (`IanuacareError`)

Module path: `ianuacare.core.exceptions`

- `IanuacareError` — base; has `message` and `code`.
- `AuthenticationError`, `AuthorizationError`, `ValidationError`, `OrchestrationError`, `InferenceError`, `StorageError`.

## Auth

Module path: `ianuacare.core.auth`

### `UserRepository`

- `get_user_by_token(token: str) -> dict` — raises `KeyError` if unknown.
- `register_token(token, user_dict)` — convenience for tests.

### `AuthService`

- `authenticate(token: str) -> User` — raises `AuthenticationError`.
- `authorize(user: User, required_permission: str) -> None` — raises `AuthorizationError`.
- `build_context(user, *, product, metadata=...)` — builds `RequestContext`.

### `CognitoLoginService`

Module path: `ianuacare.core.auth.cognito_login` — also re-exported from `ianuacare`.

Requires optional dependency **`pip install "ianuacare[aws]"`** (or `boto3`).

- Constructor: `CognitoLoginService(region, app_client_id, *, client_secret=None)`
  - Pass `client_secret` when the Cognito app client is **confidential** (computes `SECRET_HASH` for `USER_PASSWORD_AUTH`).
- `login(username: str, password: str) -> LoginTokens` — calls Cognito `InitiateAuth` with `USER_PASSWORD_AUTH`.
  - On invalid credentials: `AuthenticationError` with `code="invalid_credentials"`.
  - On throttling: `code="rate_limited"`.
  - If Cognito returns a **challenge** (e.g. `NEW_PASSWORD_REQUIRED`, MFA): `code="cognito_challenge"` — handle `RespondToAuthChallenge` in the application layer if needed.
  - Other Cognito client errors: `code="cognito_error"`.

Typical flow: `login()` → use `LoginTokens.access_token` with `AuthService` + `CognitoUserRepository`.

## Infrastructure: Cognito (`ianuacare.infrastructure.auth`)

Module path: `ianuacare.infrastructure.auth`

Requires **`[aws]`** (`boto3`; token validation also needs `python-jose`).

### `CognitoUserRepository`

- Constructor: `CognitoUserRepository(region, user_pool_id, app_client_id)` (pool/client ids are stored for alignment with your config; `get_user` uses the access token).
- `get_user_by_token(token: str) -> dict` — `get_user` + JWT claims for `role` / `permissions` custom attributes.

### `CognitoPasswordAuthenticator`

Lower-level adapter used by `CognitoLoginService`:

- `initiate_user_password_auth(username, password) -> dict` — raw `initiate_auth` response; maps `ClientError` to `AuthenticationError` as above.

## Pipeline

Module path: `ianuacare.core.pipeline`

### `DataManager`

- `collect(input_data, context: RequestContext) -> DataPacket`

### `DataValidator`

- `validate(packet: DataPacket) -> DataPacket` — sets `validated_data`; raises `ValidationError` if `raw_data` is missing (unless `allow_none_raw=True`).

### `Pipeline`

- `run(input_data, context: RequestContext) -> DataPacket` — full pipeline.

## Orchestration

Module path: `ianuacare.core.orchestration`

### `DataParser`

- `parse(packet: DataPacket) -> DataPacket` — default copies `validated_data` → `parsed_data`; override `_parse_impl` for custom parsing.

### `Orchestrator`

- `execute(packet, context) -> DataPacket` — parse, select model, run inference, set `processed_data` and `inference_result`.
- `_select_model(context, packet) -> str` — uses `context.metadata["model_key"]`, `packet.metadata["model_key"]`, `default_model_key`, or a single registered model.
- Optional cache integration via `cache: CacheClient | None` and `cache_ttl_seconds`.

## AI

Module paths: `ianuacare.ai`, `ianuacare.ai.nlp`, `ianuacare.ai.cv`, `ianuacare.ai.tabular`

### `BaseAIModel` (abstract)

- `run(payload: Any) -> Any` — implement in subclasses.

### `AIProvider`

- `infer(model_name: str, payload: Any) -> dict` — default echoes payload; replace with HTTP/SDK calls.

### `NLPModel`

- `run(payload) -> Any` — delegates to `provider.infer(model_name, payload)`.

## Storage

Module path: `ianuacare.infrastructure.storage`

### Protocols

- `DatabaseClient`: `write(collection, record) -> dict`, `fetch_all(collection) -> list`
- `BucketClient`: `upload(key, content) -> dict`, `download(key) -> Any`

### Implementations

- `InMemoryDatabaseClient`, `InMemoryBucketClient`
- `PostgresDatabaseClient` (optional dependency: `psycopg`)
- `S3BucketClient` (optional dependency: `boto3`)

### `Writer`

- `write_raw(packet, context) -> dict`
- `write_processed(packet, context) -> dict`
- `write_result(packet, context) -> dict`
- `write_log(message, context) -> dict` — **message must not contain PHI**.
- Optional `encryption: EncryptionService | None` at constructor time.

Raises `StorageError` on failure.

## Audit

Module path: `ianuacare.core.audit`

### `AuditService`

- `log_event(event_name: str, context: RequestContext, details: dict | None) -> None`

Writes to collection `audit_events`. **Do not** put PHI in `details`.

## Config

Module path: `ianuacare.core.config`

### `ConfigService`

- `get(key, default=None) -> Any`
- `set(key, value)` — for tests/dynamic config.

### `EnvConfigService`

- `get(key, default=None)` reads in-memory config first, then `IANUA_<KEY>` env vars.

## Logging

Module path: `ianuacare.core.logging`

### `StructuredLogger`

- `info()`, `warning()`, `error()` emit JSON logs with contextual fields.

## Presets

Module path: `ianuacare.presets`

### `create_stack(...)`

- Factory that wires `AuthService`, `Writer`, `Orchestrator`, and `Pipeline` from injected adapters.
