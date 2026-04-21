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
- `run_vector(operation, input_data, context: RequestContext) -> DataPacket` — vector flow:
  - write ops: `upsert` / `delete` use `Writer`
  - read ops: `search` and `scroll` use `Reader`
  - `search` supports `vector` (precomputed) or `prompt` (embedded on-the-fly via `Orchestrator.embed_text`)
  - `search`: `filters.level` is required (`text`, `sentence`, `words`)
  - `scroll`: lists all points in the collection (paginated internally); optional `filters` for exact-match payload fields; with `QdrantDatabaseClient`, uses the official client's `scroll` API until all pages are consumed

## Orchestration

Module path: `ianuacare.core.orchestration`

### `InputDataParser`

- `parse(packet: DataPacket, *, model_key: str | None = None) -> DataPacket` — sets `parsed_data` from `validated_data`; when `model_key` is set, the default implementation maps inputs to the provider payload (for example `llm` → `{"prompt": "", "text": ...}`, `diarization` → `segments` plus optional `audio_path`, `num_speakers`, `language`, `response_format`). Override `_parse_impl(validated, *, model_key)` for custom parsing.

### `OutputDataParser`

- `parse(packet: DataPacket, *, model_key: str | None = None, schema: Mapping | None = None) -> DataPacket` — reads `inference_result`, runs model-specific post-processing (branching by `model_key`), and writes the normalized value to `processed_data`.
- Branch `llm`: when `schema` is provided, validates required fields (`schema["required"]`) and top-level property types (`schema["properties"][name]["type"]`, supporting `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`, and list-of-types for unions). When `schema is None`, only normalization is applied.
- Branch `diarization`: only normalization (hook available for future post-processing).
- Branch `text_embedder`: wraps output as `{"artefatti": [ ... ]}`.
- Default branch: only normalization.
- Normalization: `dict` results are copied; non-dict results are wrapped as `{"output": result}`.

### `Orchestrator`

- `execute(packet, context) -> DataPacket` — select model, parse input with `model_key`, run inference, then parse output (with optional JSON schema read from `context.metadata["output_schema"]`) and set `processed_data` and `inference_result`.
- `_select_model(context, packet) -> str` — uses `context.metadata["model_key"]`, `packet.metadata["model_key"]`, `default_model_key`, or a single registered model.
- Constructor takes `input_parser: InputDataParser` and `output_parser: OutputDataParser` (separate stages around the model).
- Optional cache integration via `cache: CacheClient | None` and `cache_ttl_seconds`; the output parser runs on both cache-hit and cache-miss paths so `processed_data` is always coherent with the schema.
- `embed_text(text, context) -> list[float]` — helper used by vector search to produce a query vector through the registered `text_embedder` model.

## AI

Module paths: `ianuacare.ai`, `ianuacare.ai.models`, `ianuacare.ai.providers`, `ianuacare.ai.parsers`

### Inference models (`ianuacare.ai.models.inference`)

- `BaseAIModel.run(payload: Any) -> Any` — abstract entry point.
- `NLPModel(provider, model_name)` — base NLP model delegating to provider.
- `Transcription.run(payload) -> dict` — `infer(...)` + `ModelOutNormalizer.normalize_transcript`.
- `LLMModel.run(payload) -> dict` — `infer(...)` + `ModelOutNormalizer.normalize_summary`.
- `LLMModel.stream(payload) -> Iterator[str]` — text fragments from `AIProvider.infer_stream`.
- `LLMModel.arun(payload) -> dict` — async via `AIProvider.ainfer` + `normalize_summary`.
- `LLMModel.astream(payload) -> AsyncIterator[str]` — chunks from `AIProvider.ainfer_stream`.
- `LLMModel.finalize_stream_text(text) -> dict` — normalizes assembled stream text like `run`.
- `TextEmbedder.run(payload) -> dict` — returns text/sentence/word vectors in a normalized artefact shape.
- `SpeakerEmbedder.run(payload) -> list[float]` — deterministic vectorization helper.
- `SpeakerClusterer.run(payload) -> list[int]` — deterministic clustering helper.
- `DiarizationModel.run(payload) -> dict` — composes transcription, parsers, embedder, clusterer.
- `LabelClusterer.run(payload) -> dict` — generic label mapping clusterer. Expects `vectors` and `label_clusters` in payload (optional aligned `texts` and `point_ids` per vector row), clusters vectors in original space, maps each cluster to the nearest label prototype (built via `TextEmbedder`), and returns `labels`, `assigned_labels`, `cluster_to_label`, PCA visualization fields (`projected_vectors`, `explained_variance_ratio`), plus echoed `texts` and `point_ids` (defaults: empty strings and `null` ids when omitted).
- `RankedLabelClusterer.run(payload) -> dict` — generic label mapping clusterer with ranked output. Expects `vectors`, `label_clusters`, optional `texts`, and optional `num_clusters`; returns `labels`, `assigned_labels`, `cluster_to_label`, and `ranked_clusters` sorted by numerosity with `count`, `percentage`, `examples` (up to 5), and optional `keywords`.

### Normalizer (`ianuacare.ai.models.normalizer`)

- `ModelOutNormalizer.normalize_transcript(raw) -> dict`
- `ModelOutNormalizer.normalize_summary(raw) -> dict`
- `ModelOutNormalizer.normalize_task(raw) -> dict`

### Providers (`ianuacare.ai.providers`)

- `AIProvider.infer(model_name, payload) -> Any` — provider contract (raw output).
- `AIProvider.infer_stream(model_name, payload) -> Iterator[str]` — optional streaming; default yields one chunk from `infer`.
- `AIProvider.ainfer(model_name, payload)` — async; default runs `infer` in a worker thread.
- `AIProvider.ainfer_stream(model_name, payload) -> AsyncIterator[str]` — async stream; default materializes `infer_stream` in a thread.
- `CallableProvider` — callable-backed provider for tests.
- `TogetherAIProvider` — Together chat completions adapter.
- `SpeechTranscriptionProvider` — file-based ASR adapter (chunking for large audio).

### Parsers (`ianuacare.ai.parsers`)

- `BaseParser.parse(data) -> Any`
- `PauseParser.parse(segments) -> list[dict]`
- `SpectralParser.parse(segment) -> dict[str, float]`

## Breaking migration notes

- `SummaryModel` was renamed to `LLMModel` (`ianuacare.ai.models.inference.LLM`). Update imports and `model_key` values (for example `"llm"` when using the default `InputDataParser` mapping).
- The single `DataParser` was split into `InputDataParser` (ex-`DataParser`) and `OutputDataParser`. `Orchestrator(parser=...)` is replaced by `Orchestrator(input_parser=..., output_parser=...)`; the old `DataParser` is no longer exported.
- Removed modules: `ianuacare.ai.base`, `ianuacare.ai.provider`, `ianuacare.ai.nlp`, `ianuacare.ai.audio`, `ianuacare.ai.cv`, `ianuacare.ai.tabular`.
- Use `CallableProvider` instead of instantiating `AIProvider` directly.
- Model outputs are normalized dictionaries stored in `DataPacket.inference_result`.

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
- `VectorDatabaseClient`:
  - `ensure_collection(name, *, vector_size, distance="Cosine") -> dict`
  - `upsert(collection, points) -> dict`
  - `search(collection, *, vector, top_k=10, filters=None, score_threshold=None) -> list[dict]`
  - `delete(collection, *, ids=None, filters=None) -> dict`
  - `scroll(collection, *, filters=None, batch_size=256, with_vectors=False, with_payload=True) -> list[dict]` — each row includes `id`; payload/vector presence matches the flags (`QdrantDatabaseClient` wraps `QdrantClient.scroll` in a loop)

### Implementations

- `InMemoryDatabaseClient`, `InMemoryBucketClient`, `InMemoryVectorDatabaseClient`
- `PostgresDatabaseClient` (optional dependency: `psycopg`) using relational columns with safe identifiers (`psycopg.sql`)
- `S3BucketClient` (optional dependency: `boto3`)
- `QdrantDatabaseClient` (optional dependency: `qdrant-client`)

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
- Optional `vector_client: VectorDatabaseClient | None` at constructor time.
- Vector write methods:
  - `write_vector_upsert(collection, artefatti, *, vector_field, context) -> dict`
  - `write_vector_delete(collection, *, ids=None, filters=None, context) -> dict`

Raises `StorageError` on failure.

### `Reader`

- `read_one(collection, *, lookup_field, lookup_value, context) -> dict | None`
- `read_many(collection, *, filters, context) -> list[dict]`
- `read_vector_search(collection, *, vector, top_k=10, filters, score_threshold=None, context) -> list[dict]`
  - requires `filters.level` (`text`, `sentence`, `words`)
- `read_vector_scroll(collection, *, filters=None, batch_size=256, with_vectors=False, with_payload=True, context) -> list[dict]` — full collection scan via `VectorDatabaseClient.scroll` (no `filters.level` requirement; optional `filters` are exact-match on payload keys when provided)

Reads through the configured `DatabaseClient`; raises `StorageError` on failure.

## Audit

Module path: `ianuacare.core.audit`

### `AuditService`

- `log_event(event_name: str, context: RequestContext, details: dict | None) -> None`

Writes to collection `audit_events`. **Do not** put PHI in `details`.

## Chatbot (`ianuacare.core.chatbot`)

Not re-exported from top-level `ianuacare`; import from `ianuacare.core.chatbot`. Overview and diagrams: see [RAG chatbot](chatbot.md).

### Types

Module path: `ianuacare.core.chatbot.message`

- **`Message`** — `role`: `user` | `assistant` | `system`; `content`: `str`.
- **`RetrievedPoint`** — `id`, `source_text`, `score`, `turn` — built from vector hits via `RetrievedPoint.from_vector_hit(hit, turn)`.

### `ConversationState`

Module path: `ianuacare.core.chatbot.chatbot`

Mutable session cache:

- `context: list[Message]` — transcript with roles; optional initial `system` message.
- `summary: str` — compressed history when size limits trigger.
- `retrieved_pool: list[RetrievedPoint]` — accumulated vector hits across turns (in-memory only).
- `turn_index: int` — completed user/assistant pair count.

Methods include `merge_and_rerank(...)`, `prune_pool(...)`, `append_turn(...)`, `total_chars()`.

### `Chatbot`

Module path: `ianuacare.core.chatbot.chatbot`

- Constructor: `reader: Reader`, `writer: Writer`, `llm: LLMModel`, keyword-only `collection`, `filters`, optional `top_k`, `score_threshold`, `rerank_top_k`, `score_decay`, `pool_max_size`, `max_context_chars`, `system_prompt`, `max_retries`, `retry_base_delay`.
- `state: ConversationState` — public session handle.
- `inference(query, query_vector, context_request: RequestContext) -> str` — synchronous turn.
- `ainference(...) -> str` — async turn (`read_vector_search` runs in a thread pool; `llm.arun` with async retry).
- `astream(...) -> AsyncIterator[str]` — stream assistant fragments, then finalize with `finalize_stream_text`, then update state once (same atomicity rules as sync).

Retrieval uses `Reader.read_vector_search` (requires `filters["level"]` in `text` / `sentence` / `words`). Cross-turn reranking merges new hits with `retrieved_pool`, dedupes by `id`, applies decay on points from earlier turns only, keeps top `rerank_top_k`. State is updated **only after** a successful LLM response. `Writer.write_log` receives a **non-PHI** JSON line (turn index and content lengths only by default).

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
- Accepts optional `vector_database: VectorDatabaseClient | None` and injects it into both `Writer` and `Reader`.
