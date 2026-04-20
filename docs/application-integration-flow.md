# Guida integrazione applicativa

Questa guida mostra come usare la libreria Ianuacare nella propria applicazione
(backend FastAPI, Flask, Django o altro). Ogni sezione corrisponde a qualcosa
che lo sviluppatore deve fare nel proprio codice.

---

## 1 — Setup: cosa istanziare all'avvio dell'app

All'avvio, l'app crea i componenti una sola volta e li tiene in memoria
(ad esempio come singleton o nel dependency injection del framework).

Servono tre gruppi di oggetti:

### Storage (dove salvare i dati)

```python
from ianuacare import PostgresDatabaseClient, S3BucketClient

db = PostgresDatabaseClient("postgresql://user:pass@host/db")
bucket = S3BucketClient("my-bucket", region="eu-west-1")
```

!!! tip "Per test e sviluppo locale"
    Usa `InMemoryDatabaseClient` e `InMemoryBucketClient` al posto dei
    client di produzione. L'API e' identica.

### Modelli AI (cosa sa fare l'app)

Ogni modello va registrato con una **chiave** (`"llm"`, `"diarization"`, ecc.).
L'app usera' quella chiave per scegliere quale modello invocare.

```python
from ianuacare import (
    CallableProvider,
    DiarizationModel,
    EmotionClusterer,
    LLMModel,
    ModelOutNormalizer,
    NLPModel,
    SpeechTranscriptionProvider,
    TextEmbedder,
    TopicClusterer,
    Transcription,
)

# LLM (generazione testo, riassunti)
llm_provider = CallableProvider(lambda model, payload: {"text": "summary..."})
llm = LLMModel(llm_provider, "gpt-4", ModelOutNormalizer())

# Diarizzazione (trascrizione audio + speaker)
speech_provider = SpeechTranscriptionProvider(client=openai_client, model="whisper-1")
transcription = Transcription(speech_provider, "whisper-1", ModelOutNormalizer())
diarization = DiarizationModel(transcription=transcription)

# NLP generico
nlp = NLPModel(CallableProvider(), "clinical-nlp-v1")

# Text embedder (vector search)
text_embedder = TextEmbedder(CallableProvider(), "text-embedding-v1")

# Emotion + topic clustering (embedding analytics)
emotion_clusterer = EmotionClusterer(text_embedder=text_embedder)
topic_clusterer = TopicClusterer(text_embedder=text_embedder)
```

### Pipeline e autenticazione (il collante)

```python
from ianuacare import (
    AuditService,
    AuthService,
    CognitoUserRepository,
    DataManager,
    DataValidator,
    InputDataParser,
    Orchestrator,
    OutputDataParser,
    Pipeline,
    Reader,
    InMemoryVectorDatabaseClient,
    Writer,
)

auth_service = AuthService(
    user_repository=CognitoUserRepository("eu-west-1", "pool-id", "client-id")
)

vector_db = InMemoryVectorDatabaseClient()

pipeline = Pipeline(
    data_manager=DataManager(),
    validator=DataValidator(),
    writer=Writer(db, bucket, vector_client=vector_db),
    reader=Reader(db, vector_client=vector_db),
    orchestrator=Orchestrator(
        input_parser=InputDataParser(),
        output_parser=OutputDataParser(),
        models={
            "llm": llm,
            "diarization": diarization,
            "nlp": nlp,
            "text_embedder": text_embedder,
            "emotion_clusterer": emotion_clusterer,
            "topic_clusterer": topic_clusterer,
        },
        default_model_key="nlp",
    ),
    audit_service=AuditService(db),
)
```

A questo punto l'app ha due oggetti da usare nelle request: `auth_service` e `pipeline`.

---

## 2 — Ad ogni richiesta: autenticare e costruire il contesto

Ogni volta che arriva una richiesta HTTP, l'app deve:

1. **Autenticare** il token (ottenere un `User`).
2. **Autorizzare** il permesso necessario.
3. **Creare il `RequestContext`** con `model_key` se serve inferenza AI.

```python
from ianuacare import CognitoLoginService, RequestContext

# Il login puo' avvenire in un endpoint dedicato
login_service = CognitoLoginService("eu-west-1", "app-client-id")
tokens = login_service.login("user@example.com", "P@ssw0rd")

# In ogni request successiva, l'app riceve l'access_token (es. header Authorization)
user = auth_service.authenticate(tokens.access_token)
auth_service.authorize(user, "pipeline:run")

# Costruisci il contesto per questa richiesta
context = RequestContext(
    user=user,
    product="my-product",
    metadata={"model_key": "llm"},
)
```

Il campo `metadata["model_key"]` dice alla pipeline **quale modello AI usare**.
Deve corrispondere a una delle chiavi registrate nell'Orchestrator (`"llm"`,
`"diarization"`, `"nlp"`, ecc.).

!!! warning "Sicurezza"
    Non loggare mai password, token completi o codici di conferma.

---

## 3 — Inferenza AI: `pipeline.run_model(...)`

Per chiedere un'inferenza AI, l'app chiama `pipeline.run_model(input_data, context)`.

### Cosa fa l'app

1. Prepara `input_data` (un dizionario con i dati da elaborare).
2. Sceglie il modello tramite `metadata={"model_key": "..."}` nel contesto.
3. Chiama `pipeline.run_model(input_data, context)`.
4. Legge il risultato da `packet.inference_result`.

### Cosa fa la libreria (automaticamente)

La pipeline si occupa di tutto il resto senza intervento dell'app:

- Valida l'input.
- Salva i dati grezzi nello storage (**artefatto raw**).
- Seleziona il modello in base a `model_key`.
- Prepara il payload nel formato atteso dal modello.
- Esegue l'inferenza tramite il provider AI.
- Salva il risultato nello storage (**artefatto processed** + **artefatto result**).
- Registra eventi di audit.
- Restituisce il `DataPacket` con tutti i risultati.

### Diagramma

```mermaid
sequenceDiagram
    participant App
    participant Pipeline
    participant Orchestrator
    participant Model
    participant Storage as Writer (DB + Bucket)

    App->>Pipeline: run_model(input_data, context)

    Note over Pipeline: Valida input
    Pipeline->>Storage: Salva dati grezzi (artefatto #1)

    Pipeline->>Orchestrator: execute(packet, context)
    Note over Orchestrator: Legge model_key dal contesto
    Note over Orchestrator: Prepara payload (InputDataParser)
    Orchestrator->>Model: run(payload)
    Model-->>Orchestrator: risultato
    Note over Orchestrator: Valida/normalizza (OutputDataParser)
    Orchestrator-->>Pipeline: inference_result + processed_data

    Pipeline->>Storage: Salva risultato (artefatti #2 e #3)
    Pipeline-->>App: DataPacket
```

### Quale `model_key` passare e cosa mettere in `input_data`

| `model_key` | Cosa passare in `input_data` | Cosa torna in `inference_result` |
|---|---|---|
| `"llm"` | `{"text": "Testo da elaborare..."}` | `{"text": "...", "key_points": [...]}` |
| `"diarization"` | `{"audio_path": "/path/file.wav", "num_speakers": 2, "language": "it"}` | `{"raw_transcription": "...", "segments": [...], "speakers": [...]}` |
| `"emotion_clusterer"` | `{"vectors": [[...], [...], ...]}` | `{"labels": [...], "emotions": [...], "cluster_to_emotion": {...}, "projected_vectors": [...], "explained_variance_ratio": [...]}` |
| `"topic_clusterer"` | `{"vectors": [[...], ...], "texts": ["...", ...], "num_clusters": 8}` | `{"labels": [...], "topics": [...], "cluster_to_topic": {...}, "ranked_clusters": [{"label": "...", "count": 0, "percentage": 0.0, "examples": [...], "keywords": [...]}]}` |
| `"nlp"` (o altro) | Qualsiasi dizionario | Dipende dal provider configurato |

!!! note "Cosa succede se non passi `model_key`"
    La pipeline usa il `default_model_key` impostato nell'Orchestrator (nel
    setup sopra era `"nlp"`). Se c'e' un solo modello registrato, usa quello.
    Altrimenti alza `OrchestrationError`.

### Esempio: generare un riassunto con LLM

```python
context = RequestContext(
    user=user,
    product="my-product",
    metadata={"model_key": "llm"},
)
packet = pipeline.run_model(
    {"text": "Testo clinico da riassumere..."},
    context,
)
print(packet.inference_result)
# {"text": "- punto A\n- punto B", "key_points": ["punto A", "punto B"]}
```

### Esempio: diarizzazione audio

```python
context = RequestContext(
    user=user,
    product="my-product",
    metadata={"model_key": "diarization"},
)
packet = pipeline.run_model(
    {
        "audio_path": "/path/to/session.wav",
        "num_speakers": 2,
        "language": "it",
    },
    context,
)

print(packet.inference_result["raw_transcription"])
for seg in packet.inference_result["segments"]:
    print(f"Speaker {seg['speaker_id']}: {seg['text']}")
```

### Esempio: NLP generico

```python
context = RequestContext(
    user=user,
    product="my-product",
    metadata={"model_key": "nlp"},
)
packet = pipeline.run_model({"text": "example input"}, context)
print(packet.inference_result)
```

Per modelli non mappati nel parser (`"nlp"` e qualsiasi altra chiave custom),
`input_data` viene passato al modello cosi' com'e', senza trasformazioni.

### Persistenza automatica (artefatti)

Ogni chiamata a `run_model` salva automaticamente **tre artefatti** su
Bucket (es. S3) + Database (es. PostgreSQL):

| # | Cosa | Quando |
|---|---|---|
| 1 | I dati grezzi dell'app (`input_data`) | Prima dell'inferenza |
| 2 | L'output elaborato del modello | Dopo l'inferenza |
| 3 | Il risultato finale | Ultimo step |

Gli artefatti sono identificati da una chiave con formato
`{product}/{user_id}/{fase}/{request_id}`, generata automaticamente dalla libreria.
L'app non deve gestire nulla.

---

## 4 — Operazioni CRUD: `pipeline.run_crud(...)`

Per creare, leggere, aggiornare o cancellare record applicativi (es. pazienti,
sessioni, configurazioni), l'app usa `pipeline.run_crud(operation, input_data, context)`.

Questo flusso **non usa l'Orchestrator**, **non esegue inferenza AI** e
**non crea artefatti**.

### Come chiamarlo

L'`input_data` e' sempre un dizionario con almeno `"collection"` (il nome della
tabella). I campi aggiuntivi dipendono dall'operazione:

| `operation` | Campi richiesti in `input_data` | Output |
|---|---|---|
| `"create"` | `collection`, `record` (dict) | Il record creato |
| `"update"` | `collection`, `lookup_field`, `lookup_value`, `updates` (dict) | Il record aggiornato |
| `"delete"` | `collection`, `lookup_field`, `lookup_value` | Conferma eliminazione |
| `"read_one"` | `collection`, `lookup_field`, `lookup_value` | Un singolo record |
| `"read_many"` | `collection`, `filters` (dict, opzionale) | Lista di record |

### Esempio: creare un paziente

```python
context = RequestContext(user=user, product="clinic-app")

packet = pipeline.run_crud(
    "create",
    {
        "collection": "patients",
        "record": {"patient_id": "p-1001", "first_name": "Mario", "last_name": "Rossi"},
    },
    context,
)
print(packet.processed_data)
```

### Esempio: cercare pazienti

```python
packet = pipeline.run_crud(
    "read_many",
    {"collection": "patients", "filters": {"last_name": "Rossi"}},
    context,
)
print(packet.processed_data)  # [{"patient_id": "p-1001", ...}, ...]
```

---

## 5 — Audio su S3: `pipeline.run_audio(...)`

Per preparare upload audio (wav/mp3) e fare retrieval dei riferimenti da DB +
S3, l'app usa `pipeline.run_audio(operation, input_data, context)`.

Questo flusso **non usa l'Orchestrator**, **non esegue inferenza AI** e salva
metadati audio su DB con chiavi S3 ricostruibili.

### Come chiamarlo

| `operation` | Campi richiesti in `input_data` | Output |
|---|---|---|
| `"prepare_upload"` | `collection`, `filename` (`.wav` o `.mp3`) | Metadata audio + `upload_url` presigned PUT |
| `"upload_direct"` | `collection`, `filename`, `content` (bytes) **oppure** `content_base64` | Upload S3 effettuato dalla libreria + metadata DB |
| `"retrieve"` | `collection`, `lookup_field`, `lookup_value` | Metadata audio + `download_url` presigned GET |

### Regole principali

- Upload single-object: il file viene caricato su S3 intero (no multipart/chunk upload).
- Object key deterministico: `{product}/{user_id}/audio/{request_id_o_audio_id}.{ext}`.
- Retrieval DB-first: prima si legge il record dal DB, poi si genera la URL di download.
- Con `upload_direct` il caricamento effettivo su S3 avviene dentro la pipeline (`bucket.upload(...)`).

### Esempio: preparare upload mp3

```python
packet = pipeline.run_audio(
    "prepare_upload",
    {"collection": "audio_records", "filename": "session_42.mp3"},
    context,
)
print(packet.processed_data["upload_url"])
```

### Esempio: upload diretto (server-side)

```python
packet = pipeline.run_audio(
    "upload_direct",
    {
        "collection": "audio_records",
        "filename": "session_42.wav",
        "content_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAABCxAgAEABAAZGF0YQAAAAA=",
    },
    context,
)
print(packet.processed_data["status"])  # uploaded
```

### Esempio: retrieval metadata + link download

```python
packet = pipeline.run_audio(
    "retrieve",
    {
        "collection": "audio_records",
        "lookup_field": "audio_id",
        "lookup_value": "aud_42",
    },
    context,
)
print(packet.processed_data["download_url"])
```

---

## 6 — Vector DB: `pipeline.run_vector(...)`

Per scrivere/cercare/cancellare embeddings nel DB vettoriale l'app usa `pipeline.run_vector(operation, input_data, context)`.

| `operation` | Campi richiesti in `input_data` | Output |
|---|---|---|
| `"upsert"` | `collection`, `artefatti`, `vector_field` (`text`/`sentence`/`words`) | conteggio upsert |
| `"search"` | `collection`, `filters.level`, `vector` **oppure** `prompt`, `top_k` opzionale | lista hit |
| `"delete"` | `collection`, `ids` **oppure** `filters` | conteggio delete |

### Esempio: upsert

```python
packet = pipeline.run_vector(
    "upsert",
    {
        "collection": "clinical_notes",
        "vector_field": "sentence",
        "artefatti": artefatti,
    },
    context,
)
print(packet.processed_data)
```

### Esempio: search by prompt

```python
packet = pipeline.run_vector(
    "search",
    {
        "collection": "clinical_notes",
        "prompt": "diabete tipo 2",
        "top_k": 5,
        "filters": {"level": "sentence"},
    },
    context,
)
print(packet.processed_data)
```

!!! note "Creazione collection"
    Con `QdrantDatabaseClient`, `upsert(...)` esegue automaticamente `ensure_collection(...)`
    se la collection non esiste, usando `distance="Cosine"` e `vector_size` derivata dal primo vettore.

---

## 7 — Gestione errori

La libreria alza eccezioni tipizzate che l'app deve catturare nel boundary
HTTP/API e mappare a codici di stato:

| Eccezione | Quando | Codice HTTP suggerito |
|---|---|---|
| `AuthenticationError` | Token invalido, credenziali errate | 401 |
| `AuthorizationError` | Permesso mancante | 403 |
| `ValidationError` | Input malformato, campi mancanti | 422 |
| `OrchestrationError` | `model_key` non valido, nessun modello selezionabile | 400 |
| `InferenceError` | Il provider AI fallisce | 502 |
| `StorageError` | Errore scrittura/lettura su database o bucket | 500 |

### Esempio: handler FastAPI/Flask

```python
from ianuacare.core.exceptions.errors import (
    AuthenticationError,
    AuthorizationError,
    InferenceError,
    ValidationError,
)

try:
    packet = pipeline.run_model(input_data, context)
except AuthenticationError:
    return {"error": "unauthorized"}, 401
except AuthorizationError:
    return {"error": "forbidden"}, 403
except ValidationError as e:
    return {"error": "bad_request", "detail": e.message}, 422
except InferenceError:
    return {"error": "model_error"}, 502
```

---

## Riepilogo

```mermaid
flowchart LR
    Login["1. Login
    → LoginTokens"] --> Auth["2. Authenticate
    → User"]
    Auth --> Ctx["3. RequestContext
    (user, product, model_key)"]
    Ctx --> Choice{Cosa deve fare l'app?}
    Choice -->|"Inferenza AI"| RunModel["run_model(input_data, context)
    → packet.inference_result"]
    Choice -->|"CRUD dati"| RunCrud["run_crud(operation, data, context)
    → packet.processed_data"]
    Choice -->|"Audio S3"| RunAudio["run_audio(operation, data, context)
    → packet.processed_data"]
    Choice -->|"Vector DB"| RunVector["run_vector(operation, data, context)
    → packet.processed_data"]
```

| Step | L'app fa | La libreria fa |
|---|---|---|
| **Setup** | Istanzia DB, bucket, modelli, pipeline | — |
| **Auth** | Passa il token | Autentica, autorizza, crea User |
| **Contesto** | Crea `RequestContext` con `model_key` | — |
| **Inferenza** | Chiama `run_model(input_data, context)` | Valida, salva, seleziona modello, parsa, inferisce, salva risultato |
| **CRUD** | Chiama `run_crud(op, data, context)` | Valida e esegue l'operazione su DB |
| **Audio S3** | Chiama `run_audio(op, data, context)` | Valida payload audio, salva metadata DB, genera URL presigned upload/download |
| **Vector DB** | Chiama `run_vector(op, data, context)` | Valida payload vector, upsert/search/delete su vector client |
| **Errori** | Cattura eccezioni e mappa a HTTP status | Alza eccezioni tipizzate |
