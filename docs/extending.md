# Extending Ianuacare

## Custom AI models

Subclass `BaseAIModel` and register instances in `Orchestrator`:

```python
from ianuacare.ai.base import BaseAIModel
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import DataParser

class VisionModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        # load image refs from payload, call your vision API, return structured output
        return {"labels": []}

orch = Orchestrator(
    DataParser(),
    {"vision": VisionModel(), "nlp": nlp_model},
    default_model_key="nlp",
)
```

Then set `RequestContext(..., metadata={"model_key": "vision"})` when routing to that model.

## Custom parsing

Subclass `DataParser` (`ianuacare.core.orchestration`) and override `_parse_impl` for schema validation, FHIR normalization, etc.:

```python
class FhirParser(DataParser):
    def _parse_impl(self, validated: object) -> dict:
        # return a normalized structure
        return {"resource": validated}
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
