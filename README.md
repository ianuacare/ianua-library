# Ianuacare

Healthcare-oriented **Python** library for data pipelines and AI inference: authentication, validation, orchestration, audit-friendly logging, and pluggable storage.

## Install

```bash
pip install -e ".[dev]"
```

## Documentation

See the [`docs/`](docs/) folder:

- [Index](docs/index.md)
- [Architecture](docs/architecture.md)
- [Getting started](docs/getting-started.md)
- [Audio transcription and diarization](docs/audio-diarization.md) (new `ianuacare.ai.models.inference` flow, optional `[audio]` extra)
- [API reference](docs/api-reference.md)
- [Preconfigurations](docs/preconfigurations.md)
- [Extending](docs/extending.md)
- [Documentation workflow](docs/documentation-workflow.md)

Build docs locally (install the **`docs`** extra so MkDocs Material matches this repo):

```bash
pip install -e ".[docs]"
mkdocs serve
```

Static site (strict; fails on documentation warnings):

```bash
mkdocs build --strict
```

## Preconfigured adapters

The library now includes production-oriented adapters and a generic stack factory:

- `CognitoUserRepository` (AWS Cognito)
- `PostgresDatabaseClient` (PostgreSQL)
- `S3BucketClient` (AWS S3)
- `TogetherAIProvider` (Together AI)
- Speech pipeline (`ianuacare.ai.models.inference` + `ianuacare.ai.providers`): `DiarizationModel`, `Transcription`, `SpeechTranscriptionProvider`, `LLMModel` (requires **`[audio]`** extra)
- `RedisCacheClient` (Redis)
- `KMSEncryptionService` (AWS KMS)
- `EnvConfigService` and `StructuredLogger`
- `create_stack(...)` in `ianuacare.presets` for vendor-agnostic wiring

Install optional dependencies as needed:

```bash
pip install -e ".[aws,postgres,together,redis,audio]"
```

## Documentation policy

Documentation updates are mandatory for every feature, refactor, or bugfix that changes behavior, API, architecture, or setup.
See [documentation workflow](docs/documentation-workflow.md).

## Quick example

```python
from ianuacare import (
    CallableProvider,
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
provider = CallableProvider()
nlp = NLPModel(provider, "clinical-nlp-v1")
pipe = Pipeline(
    DataManager(),
    DataValidator(),
    writer,
    Reader(db),
    Orchestrator(DataParser(), {"nlp": nlp}, default_model_key="nlp"),
    AuditService(db),
)
ctx = RequestContext(User("u1", "clinician", ["pipeline:run"]), "ianuacare-demo")
packet = pipe.run({"text": "example"}, ctx)
```

## License

MIT
