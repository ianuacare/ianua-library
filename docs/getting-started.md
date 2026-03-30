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
    RequestContext,
    User,
    Writer,
)

db = InMemoryDatabaseClient()
bucket = InMemoryBucketClient()
writer = Writer(db, bucket)
provider = AIProvider()
nlp = NLPModel(provider, "clinical-nlp-v1")

pipe = Pipeline(
    data_manager=DataManager(),
    validator=DataValidator(),
    writer=writer,
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
