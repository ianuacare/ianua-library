# Extending Ianuacare

## Custom AI models

Subclass `BaseAIModel` and register instances in `Orchestrator`:

```python
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser

class VisionModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        # load image refs from payload, call your vision API, return structured output
        return {"labels": []}

orch = Orchestrator(
    InputDataParser(),
    OutputDataParser(),
    {"vision": VisionModel(), "nlp": nlp_model},
    default_model_key="nlp",
)
```

Then set `RequestContext(..., metadata={"model_key": "vision"})` when routing to that model.

## Custom speech-to-text

Use `SpeechTranscriptionProvider` for ASR, then plug it into `Transcription(provider, model_name, normalizer)`.
`DiarizationModel` composes `Transcription`, `PauseParser`, `SpectralParser`, `SpeakerEmbedder`, and `SpeakerClusterer`.

`LLMModel` also uses the same provider + normalizer pattern (`infer` + normalize).

## Custom parsing

The orchestration stage wires two parsers:

- `InputDataParser` — transforms `validated_data` into the provider payload (`parsed_data`).
- `OutputDataParser` — transforms the model's `inference_result` into `processed_data`, runs optional JSON-schema checks for `llm`, and applies the final normalization.

Subclass `InputDataParser` (`ianuacare.core.orchestration`) and override `_parse_impl` for schema validation, FHIR normalization, etc. The default `Orchestrator` passes `model_key` so you can branch per registered model:

```python
class FhirParser(InputDataParser):
    def _parse_impl(self, validated: object, *, model_key: str | None = None) -> dict:
        # return a normalized structure
        return {"resource": validated}
```

Subclass `OutputDataParser` to run extra post-inference checks or transformations. For the built-in `llm` branch, pass a JSON schema via `context.metadata["output_schema"]` (supports `required` and top-level `properties.<name>.type`) and the parser will validate coherence before normalization; when no schema is provided, the `llm` branch only normalizes:

```python
ctx = RequestContext(
    user,
    "my-product",
    metadata={
        "model_key": "llm",
        "output_schema": {
            "required": ["summary"],
            "properties": {
                "summary": {"type": "string"},
                "score": {"type": "number"},
            },
        },
    },
)
```

## Custom validation

Subclass `DataValidator` (`ianuacare.core.pipeline`) and override `_coerce_validated` or `validate` to integrate Pydantic/Marshmallow schemas and raise `ValidationError` with clear messages (avoid echoing PHI in error strings in production).

## Production storage

Implement `DatabaseClient` and `BucketClient` from `ianuacare.infrastructure.storage` with your drivers (e.g. SQLAlchemy, boto3). Keep **collection names** and key conventions consistent with your retention and backup policies.

`DatabaseClient` now includes CRUD primitives used by `Reader`/`Writer`:

- `create(collection, record)`
- `read_one(collection, *, key, value)`
- `read_many(collection, *, filters=None)`
- `update(collection, *, key, value, updates)`
- `delete(collection, *, key, value)`

Compatibility methods `write` and `fetch_all` are still available.

`Writer` uses blob keys of the form:

`{product}/{user_id}/{phase}/{request_id}`

Ensure `request_id` is set (automatically by `DataManager.collect()`).

## Cache and encryption extensions

- Implement `CacheClient` (`ianuacare.infrastructure.cache`) to plug custom caches into `Orchestrator`.
- Implement `EncryptionService` (`ianuacare.infrastructure.encryption`) to encrypt blobs before `Writer` uploads.

Built-in adapters include `RedisCacheClient` and `KMSEncryptionService`.

## Preset assembly

Use `create_stack()` (`ianuacare.presets`) to assemble framework services from your adapters, while keeping the core vendor-agnostic.

The stack now wires both `Writer` and `Reader` into `Pipeline` (`run_model` and `run_crud` flows).

## Authentication in API layers

### Bearer token (already issued)

Call `AuthService.authenticate()` (`ianuacare.core.auth`) on incoming tokens, then `authorize()` for the permission required by the endpoint (e.g. `pipeline:run` or domain-specific CRUD permission), then build `RequestContext` and call `Pipeline.run_model()` or `Pipeline.run_crud()`.

### AWS Cognito (`USER_PASSWORD_AUTH`)

Use `CognitoLoginService` to exchange username/password for `LoginTokens`, then `AuthService` with `CognitoUserRepository` on `tokens.access_token`. Keep **passwords and tokens out of logs**; map `AuthenticationError.code` (`invalid_credentials`, `cognito_challenge`, `rate_limited`, etc.) to HTTP responses in your API layer.

If Cognito returns `cognito_challenge`, implement `RespondToAuthChallenge` (or hosted UI) in the application — the library stops at surfacing that code.

### Self-registration (`SignUp`)

Use `CognitoRegistrationService.register()` then `confirm()` when `UserConfirmed` is false in your pool policy. Map `ValidationError.code` for client-facing messages (e.g. `username_exists`, `invalid_password`). Admin-only flows (`AdminCreateUser`) are not wrapped here — call boto3 from your backend if you use them.

### Password reset, session, and profile

`CognitoAccountService` wraps `ForgotPassword`, `ConfirmForgotPassword`, `GlobalSignOut`, `ChangePassword`, and `UpdateUserAttributes`. After `logout`, drop the access token on the client; Cognito may still honor it until expiry. For email/phone updates that require verification, Cognito may return a confirmation flow — handle `GetUserAttributeVerificationToken` / `VerifyUserAttribute` in your app if needed (not wrapped in this library).

## Audit and compliance

- Treat `AuditService.log_event` as **operational** metadata: user id, product, event name, correlation ids.
- For regulatory audit trails, combine this with immutable storage and access controls outside this library.
