# Preconfigurations

Ianuacare now ships production-oriented adapters and a vendor-agnostic stack factory.

## Available adapters

### :material-shield-account: Auth

- :fontawesome-brands-aws: `CognitoUserRepository` (`ianuacare.infrastructure.auth`) — resolves a principal from a **Cognito access token** (and JWT claim attributes).
- :fontawesome-brands-aws: `CognitoLoginService` (`ianuacare.core.auth`, re-exported from `ianuacare`) — **password login** via `USER_PASSWORD_AUTH`, returns `LoginTokens`.
- :fontawesome-brands-aws: `CognitoPasswordAuthenticator` (`ianuacare.infrastructure.auth`) — low-level `InitiateAuth` wrapper (used by `CognitoLoginService`).
- :fontawesome-brands-aws: `CognitoRegistrationService` (`ianuacare.core.auth`) — self-service `SignUp` / `ConfirmSignUp`.
- :fontawesome-brands-aws: `CognitoRegistrationClient` (`ianuacare.infrastructure.auth`) — low-level registration wrapper.
- :fontawesome-brands-aws: `CognitoAccountService` (`ianuacare.core.auth`) — forgot/reset password, global sign-out, change password, update attributes.
- :fontawesome-brands-aws: `CognitoAccountClient` (`ianuacare.infrastructure.auth`) — low-level account/session calls.

All require the **`aws`** extra (`pip install "ianuacare[aws]"` or equivalent): `boto3`, and `python-jose` for JWT claim reads in `CognitoUserRepository`.

### :material-database: Storage

- :simple-postgresql: `PostgresDatabaseClient` (`ianuacare.infrastructure.storage`) for relational persistence with dynamic columns (safe identifiers via `psycopg.sql`).
- :material-database-search: `QdrantDatabaseClient` (`ianuacare.infrastructure.storage`) for vector persistence, similarity search, and full-collection `scroll` (optional `qdrant` extra).
- :fontawesome-brands-aws: `S3BucketClient` (`ianuacare.infrastructure.storage`) for blob/object storage.
- `Reader` and `Writer` (`ianuacare.infrastructure.storage`) for CRUD reads/writes, vector reads/writes, and pipeline artifact persistence over `DatabaseClient`/`VectorDatabaseClient`.

### :material-robot-outline: AI provider

- :material-brain: `TogetherAIProvider` (`ianuacare.ai.providers`) for Together chat inference and embeddings (`pip install "ianuacare[together]"`).
- :material-api: `RestHostedModelProvider` (`ianuacare.ai.providers`) for custom REST-hosted models (injectable request/response hooks; stdlib HTTP).
- :material-server-network: `SelfHostedEmbeddingProvider` (`ianuacare.ai.providers`) for text embeddings served by your own REST endpoint (stdlib HTTP, no extra dependency).

#### Self-hosted text embeddings

The provider posts `{"model": model_name, "payload": {"texts": [...]}}` and reads back `embeddings`, the `list[list[float]]` shape `TextEmbedder` expects. Long inputs are split into `batch_size` requests and reassembled in order.

```python
from ianuacare import SelfHostedEmbeddingProvider, TextEmbedder

documents = SelfHostedEmbeddingProvider(
    "http://localhost:8012/infer",
    api_key=os.environ.get("EMBEDDING_API_KEY"),
    dimensions=1024,
)

embedder = TextEmbedder(provider=documents, model_name="qwen3-embedding")
artefact = embedder.run(
    {
        "id_artefatto_trascrizione": "tr-1",
        "text": "Il paziente riferisce miglioramenti del sonno.",
        "chunks": ["Il paziente riferisce miglioramenti del sonno."],
    }
)
```

Endpoints that format queries differently from documents (for example with an instruction prefix) need a second instance. `TextEmbedder` never forwards `params`, so the distinction lives in the constructor: wire the `document` instance into indexing and the `query` one into search, keeping the same model and `dimensions` on both.

```python
queries = SelfHostedEmbeddingProvider(
    "http://localhost:8012/infer",
    input_type="query",
    instruction="Find relevant document passages that answer the user's search query.",
    dimensions=1024,
)
query_vector = queries.infer("qwen3-embedding", "Come sta dormendo il paziente?")[0]
```

Per-call `params` override the constructor defaults, so a single instance can still serve both modes: `provider.infer(model, texts, params={"input_type": "query"})`.

#### LLM generation parameters

`LLMModel` accepts construction-time keyword arguments for generation: `temperature` (default `0.7`), `top_p` (default `1.0`), `top_k`, `max_tokens`, `stop`, `seed`, `frequency_penalty`, `presence_penalty`, `repetition_penalty`, `reasoning_effort`, `reasoning_enabled`, `response_format`, and `extra` (provider-specific passthrough, e.g. Together `chat_template_kwargs`).

```python
import os

from ianuacare import LLMModel, ModelOutNormalizer, TogetherAIProvider

together = TogetherAIProvider(
    api_key=os.environ["TOGETHER_API_KEY"],
    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    default_params={"temperature": 0.3},  # optional provider-level defaults
)

llm = LLMModel(
    together,
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ModelOutNormalizer(),
    temperature=0.2,
    top_p=0.9,
    reasoning_effort="medium",
    response_format={"type": "json_object"},
)
```

Provider-agnostic: each backend maps supported keys; unset params are omitted (except `LLMModel` defaults for `temperature` / `top_p`). `response_format` steers the provider API; pipeline validation uses `context.metadata["output_schema"]` separately.

Full reference: [LLM generation parameters](llm-generation-params.md).

### :material-microphone: Speech (transcription / diarization / transcript summary)

- Modules **`ianuacare.ai.models.inference`**, **`ianuacare.ai.providers`**, **`ianuacare.ai.models.normalizer`** (optional **`audio`** extra: `pip install "ianuacare[audio]"`).
- Main classes: `Transcription`, `DiarizationModel`, `LLMModel`, `TextEmbedder`, `LabelClusterer`, `RankedLabelClusterer`, `SpeechTranscriptionProvider`, `ModelOutNormalizer`.
- See [Audio transcription and diarization](audio-diarization.md) for usage; apps wire provider + normalizer, while models stay vendor-agnostic.

### :material-emoticon-happy-outline: Audio emotion (REST-hosted)

- `AudioEmotionModel`, `RestHostedModelProvider`, `RestRequest`, `ModelOutNormalizer.normalize_audio_emotion`.
- No dedicated pip extra; endpoint contract is defined in your app via `build_request` / `parse_response`.
- See [Audio emotion (REST-hosted models)](audio-emotion.md).

### :material-lightning-bolt-circle: Cache and encryption

- `CacheClient` + `InMemoryCacheClient` (`ianuacare.infrastructure.cache`)
- :simple-redis: `RedisCacheClient` (`ianuacare.infrastructure.cache.redis`)
- `EncryptionService` + `NoOpEncryption` (`ianuacare.infrastructure.encryption`)
- :fontawesome-brands-aws: `KMSEncryptionService` (`ianuacare.infrastructure.encryption.kms`)

### :material-cog-outline: Configuration and logging

- `EnvConfigService` (`ianuacare.core.config`) reads `IANUA_*` environment variables.
- :material-math-log: `StructuredLogger` (`ianuacare.core.logging`) emits JSON logs with context fields.

## Generic factory

Use `create_stack()` to wire the framework without vendor lock-in:

```python
from ianuacare import (
    InMemoryBucketClient,
    InMemoryDatabaseClient,
    NLPModel,
    CallableProvider,
    UserRepository,
    create_stack,
)

provider = CallableProvider()
model = NLPModel(provider, "clinical")

stack = create_stack(
    auth_repository=UserRepository(),
    database=InMemoryDatabaseClient(),
    bucket=InMemoryBucketClient(),
    models={"nlp": model},
    default_model_key="nlp",
    vector_database=None,  # pass InMemoryVectorDatabaseClient or QdrantDatabaseClient when needed
)

# stack.pipeline, stack.auth_service, stack.writer, stack.orchestrator
```

For production, pass concrete adapters (Cognito/Postgres/S3/Redis/KMS) instead of in-memory ones.
