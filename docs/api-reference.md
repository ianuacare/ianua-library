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

### `RegistrationResult`

Module path: `ianuacare.core.models.registration_result`

- `user_sub: str` — Cognito `UserSub`.
- `user_confirmed: bool` — `True` if no further confirmation step is required for the user pool policy.

### `PasswordResetDelivery`

Module path: `ianuacare.core.models.password_reset_delivery`

- `destination: str` — masked destination from Cognito (`CodeDeliveryDetails`).
- `delivery_medium: str` — e.g. `EMAIL`, `SMS`.

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

### `CognitoRegistrationService`

Module path: `ianuacare.core.auth.cognito_registration` — also re-exported from `ianuacare`.

Requires **`[aws]`** (`boto3`). The user pool must allow **self-registration** on the app client.

- Constructor: `CognitoRegistrationService(region, app_client_id, *, client_secret=None)`.
- `register(username, password, *, attributes=None) -> RegistrationResult` — Cognito `SignUp`.
  - `attributes`: optional `dict` of Cognito attribute names to values (e.g. `email`, `phone_number`).
  - Failures: mostly `ValidationError` (`username_exists`, `invalid_password`, `invalid_parameter`, `user_lambda_validation`, `cognito_error`); throttling uses `AuthenticationError` with `code="rate_limited"`.
- `confirm(username, confirmation_code) -> None` — Cognito `ConfirmSignUp` after email/SMS code.
  - Failures: `ValidationError` (`invalid_confirmation_code`, `expired_confirmation_code`, `confirm_not_allowed`, `user_not_found`, `alias_exists`, …); rate limit as above.

After `user_confirmed` is true (or after `confirm()`), the user can call `CognitoLoginService.login()`.

### `CognitoAccountService`

Module path: `ianuacare.core.auth.cognito_account` — also re-exported from `ianuacare`.

Requires **`[aws]`** (`boto3`).

- Constructor: `CognitoAccountService(region, app_client_id, *, client_secret=None)`.
- `request_password_reset(username) -> PasswordResetDelivery` — `ForgotPassword` (user receives a code).
- `confirm_password_reset(username, confirmation_code, new_password) -> None` — `ConfirmForgotPassword`.
- `logout(access_token) -> None` — `GlobalSignOut` (invalidates **refresh** tokens for the user; access token may still work until expiry — discard it client-side).
- `change_password(access_token, previous_password, new_password) -> None` — `ChangePassword` for a signed-in user.
- `update_profile_attributes(access_token, attributes: dict[str, str]) -> None` — `UpdateUserAttributes` (standard and custom attribute names as Cognito expects).

Errors combine `ValidationError` and `AuthenticationError` (e.g. `invalid_token`, `invalid_credentials`, `rate_limited`, `invalid_password`, `alias_exists`, `limit_exceeded`, `password_reset_required`). See Cognito docs for pool-specific behavior.

## Infrastructure: Cognito (`ianuacare.infrastructure.auth`)

Module path: `ianuacare.infrastructure.auth`

Requires **`[aws]`** (`boto3`; token validation also needs `python-jose`).

### `CognitoUserRepository`

- Constructor: `CognitoUserRepository(region, user_pool_id, app_client_id)` (pool/client ids are stored for alignment with your config; `get_user` uses the access token).
- `get_user_by_token(token: str) -> dict` — `get_user` + JWT claims for `role` / `permissions` custom attributes.

### `CognitoPasswordAuthenticator`

Lower-level adapter used by `CognitoLoginService`:

- `initiate_user_password_auth(username, password) -> dict` — raw `initiate_auth` response; maps `ClientError` to `AuthenticationError` as above.

### `CognitoRegistrationClient`

Lower-level adapter used by `CognitoRegistrationService`:

- `sign_up(username, password, *, attributes=None) -> dict` — boto3 `sign_up` response.
- `confirm_sign_up(username, confirmation_code) -> None` — wraps `confirm_sign_up`.
- Maps `ClientError` to `ValidationError` / `AuthenticationError` (rate limits) as documented for `CognitoRegistrationService`.

### `CognitoAccountClient`

Lower-level adapter used by `CognitoAccountService`:

- `forgot_password`, `confirm_forgot_password`, `global_sign_out`, `change_password`, `update_user_attributes`.

## Pipeline

Module path: `ianuacare.core.pipeline`

### `DataManager`

- `collect(input_data, context: RequestContext) -> DataPacket`

### `DataValidator`

- `validate(packet: DataPacket) -> DataPacket` — sets `validated_data`; raises `ValidationError` if `raw_data` is missing (unless `allow_none_raw=True`).

### `Pipeline`

- Constructor now requires: `data_manager`, `validator`, `writer`, `reader`, `orchestrator`, `audit_service`.
- `run(input_data, context: RequestContext) -> DataPacket` — backward-compatible alias of `run_model`.
- `run_model(input_data, context: RequestContext) -> DataPacket` — full model flow (`collect -> validate -> write_raw -> orchestrate -> write_processed -> write_result`).
- `run_crud(operation, input_data, context: RequestContext) -> DataPacket` — CRUD flow:
  - write ops (`create`, `update`, `delete`) use `Writer`
  - read ops (`read_one`, `read_many`) use `Reader`
  - result is set in `packet.processed_data` consistently.

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

- `DatabaseClient`:
  - `create(collection, record) -> dict`
  - `read_one(collection, *, key, value) -> dict | None`
  - `read_many(collection, *, filters=None) -> list[dict]`
  - `update(collection, *, key, value, updates) -> dict`
  - `delete(collection, *, key, value) -> dict`
  - legacy compatibility: `write(...)`, `fetch_all(...)`
- `BucketClient`: `upload(key, content) -> dict`, `download(key) -> Any`

### Implementations

- `InMemoryDatabaseClient`, `InMemoryBucketClient`
- `PostgresDatabaseClient` (optional dependency: `psycopg`) using relational columns with safe identifiers (`psycopg.sql`)
- `S3BucketClient` (optional dependency: `boto3`)

### `Writer`

- `write_raw(packet, context) -> dict`
- `write_processed(packet, context) -> dict`
- `write_result(packet, context) -> dict`
- `write_log(message, context) -> dict` — **message must not contain PHI**.
- CRUD write methods:
  - `write_create(collection, payload, context) -> dict`
  - `write_update(collection, *, lookup_field, lookup_value, updates, context) -> dict`
  - `write_delete(collection, *, lookup_field, lookup_value, context) -> dict`
- Optional `encryption: EncryptionService | None` at constructor time.

Raises `StorageError` on failure.

### `Reader`

- `read_one(collection, *, lookup_field, lookup_value, context) -> dict | None`
- `read_many(collection, *, filters, context) -> list[dict]`

Reads through the configured `DatabaseClient`; raises `StorageError` on failure.

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

- Factory that wires `AuthService`, `Writer`, `Reader`, `Orchestrator`, and `Pipeline` from injected adapters.
