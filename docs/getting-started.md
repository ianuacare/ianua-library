# Getting started

## Requirements

- Python **3.12+**

## Install

From the repository root:

```bash
pip install -e ".[dev]"
```

### Optional: AWS (Cognito, S3, …)

```bash
pip install -e ".[dev,aws]"
```

## Minimal example

```python
from ianuacare import (
    AIProvider,
    AuditService,
    DataManager,
    DataParser,
    DataValidator,
    InMemoryBucketClient,
    InMemoryDatabaseClient,
    NLPModel,
    Orchestrator,
    Pipeline,
    Reader,
    RequestContext,
    User,
    Writer,
)

db = InMemoryDatabaseClient()
bucket = InMemoryBucketClient()
writer = Writer(db, bucket)
reader = Reader(db)
provider = AIProvider()
nlp = NLPModel(provider, "clinical-nlp-v1")

pipe = Pipeline(
    data_manager=DataManager(),
    validator=DataValidator(),
    writer=writer,
    reader=reader,
    orchestrator=Orchestrator(
        DataParser(),
        {"nlp": nlp},
        default_model_key="nlp",
    ),
    audit_service=AuditService(db),
)

ctx = RequestContext(
    User("u1", "clinician", ["pipeline:run"]),
    "my-product",
    metadata={"model_key": "nlp"},
)
packet = pipe.run({"text": "example input"}, ctx)
print(packet.inference_result)
```

## CRUD flow example

`Pipeline.run_crud(...)` executes CRUD operations through storage adapters:

```python
from ianuacare import (
    AuditService,
    DataManager,
    DataParser,
    DataValidator,
    InMemoryBucketClient,
    InMemoryDatabaseClient,
    Orchestrator,
    Pipeline,
    Reader,
    RequestContext,
    User,
    Writer,
)
from ianuacare.ai.base import BaseAIModel


class NoOpModel(BaseAIModel):
    def run(self, payload: object) -> dict:
        return {"ok": True}


db = InMemoryDatabaseClient()
writer = Writer(db, InMemoryBucketClient())
reader = Reader(db)
pipe = Pipeline(
    DataManager(),
    DataValidator(),
    writer,
    reader,
    Orchestrator(DataParser(), {"noop": NoOpModel()}, default_model_key="noop"),
    AuditService(db),
)
ctx = RequestContext(User("u1", "operator", ["patients:create"]), "clinic-app")

created = pipe.run_crud(
    "create",
    {
        "collection": "patients",
        "record": {"patient_id": "p-1001", "first_name": "Mario", "last_name": "Rossi"},
    },
    ctx,
)
print(created.processed_data)
```

### Cognito: password login + token authentication

With `boto3` installed (`[aws]`), you can obtain tokens and reuse `AuthService` with `CognitoUserRepository`:

```python
from ianuacare import AuthService, CognitoLoginService, CognitoUserRepository

login = CognitoLoginService(
    "eu-west-1",
    "your-app-client-id",
    client_secret=None,  # set if the app client has a secret
)
tokens = login.login("user@example.com", "password")

auth = AuthService(
    CognitoUserRepository(
        "eu-west-1",
        "your-user-pool-id",
        "your-app-client-id",
    )
)
user = auth.authenticate(tokens.access_token)
```

Do not log passwords or full tokens; treat `LoginTokens` as secrets in your app.

### Cognito: self-registration and confirmation

```python
from ianuacare import CognitoRegistrationService

reg = CognitoRegistrationService(
    "eu-west-1",
    "your-app-client-id",
    client_secret=None,
)
result = reg.register(
    "user@example.com",
    "ValidP@ssw0rd1",
    attributes={"email": "user@example.com"},
)
if not result.user_confirmed:
    reg.confirm("user@example.com", code_from_email)
```

Pool and app client must allow sign-up; do not log confirmation codes.

### Cognito: reset password, logout, change password, profile

```python
from ianuacare import CognitoAccountService, CognitoLoginService

account = CognitoAccountService("eu-west-1", "your-app-client-id")
delivery = account.request_password_reset("user@example.com")
# show delivery.destination / delivery.delivery_medium to the user (masked)
account.confirm_password_reset("user@example.com", "123456", "NewValidP@ss1")

tokens = CognitoLoginService("eu-west-1", "your-app-client-id").login(
    "user@example.com", "NewValidP@ss1"
)
account.change_password(tokens.access_token, "NewValidP@ss1", "AnotherValidP@ss2")
account.update_profile_attributes(tokens.access_token, {"given_name": "Ada"})
account.logout(tokens.access_token)
```

Do not log passwords, codes, or raw tokens.

## Run tests

```bash
pytest

# With coverage (matches CI expectations)
pytest --cov=ianuacare --cov-report=term-missing
```

## Lint and types

```bash
ruff check src tests
mypy src
```

## Next steps

- Read [API reference](api-reference.md) for class details.
- Read [Preconfigurations](preconfigurations.md) for production-ready adapters.
- Read [Extending](extending.md) to add custom models and validation.
