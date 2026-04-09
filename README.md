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
- [Audio transcription and diarization](docs/audio-diarization.md) (`ianuacare.ai.audio`, optional `[audio]` extra)
- [API reference](docs/api-reference.md)
- [Preconfigurations](docs/preconfigurations.md)
- [Extending](docs/extending.md)
- [Documentation workflow](docs/documentation-workflow.md)

Build docs locally:

```bash
mkdocs serve
```

## Preconfigured adapters

The library now includes production-oriented adapters and a generic stack factory:

- `CognitoUserRepository` (AWS Cognito)
- `PostgresDatabaseClient` (PostgreSQL)
- `S3BucketClient` (AWS S3)
- `TogetherAIProvider` (Together AI)
- Speech pipeline (`ianuacare.ai.audio`): `DiarizationPipeline`, `SpeechTranscriber`, `OpenAISpeechTranscriber`, `SummaryGenerator` (requires **`[audio]`** extra)
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
    DataManager(),
    DataValidator(),
    writer,
    Orchestrator(DataParser(), {"nlp": nlp}, default_model_key="nlp"),
    AuditService(db),
)
ctx = RequestContext(User("u1", "clinician", ["pipeline:run"]), "ianuacare-demo")
packet = pipe.run({"text": "example"}, ctx)
```

## License

MIT
