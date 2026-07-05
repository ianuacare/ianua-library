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
    AudioEmotionModel,
    CallableProvider,
    DiarizationModel,
    LabelClusterer,
    LLMModel,
    ModelOutNormalizer,
    NLPModel,
    RankedLabelClusterer,
    RestHostedModelProvider,
    RestRequest,
    SpeechTranscriptionProvider,
    TextEmbedder,
    Transcription,
)

# LLM (generazione testo, riassunti)
llm_provider = CallableProvider(lambda model, payload: {"text": "summary..."})
# I parametri di generazione si impostano alla costruzione del modello.
# Vengono inviati solo quelli valorizzati (gli altri usano i default del modello);
# `temperature` e `top_p` hanno un default integrato.
llm = LLMModel(
    llm_provider,
    "gpt-4",
    ModelOutNormalizer(),
    temperature=0.2,
    top_p=0.9,
    reasoning_effort="medium",          # "low" | "medium" | "high"
    reasoning_enabled=True,             # toggle per i modelli "hybrid"
    response_format={"type": "json_object"},  # output format (structured outputs)
    extra={"chat_template_kwargs": {"thinking": True}},  # knob provider-specifici
)

# Diarizzazione (trascrizione audio + speaker)
speech_provider = SpeechTranscriptionProvider(client=openai_client, model="whisper-1")
transcription = Transcription(speech_provider, "whisper-1", ModelOutNormalizer())
diarization = DiarizationModel(transcription=transcription)

# NLP generico
nlp = NLPModel(CallableProvider(), "clinical-nlp-v1")

# Text embedder (vector search)
text_embedder = TextEmbedder(CallableProvider(), "text-embedding-v1")

# Generic label clustering (embedding analytics)
label_clusterer = LabelClusterer(text_embedder=text_embedder)
ranked_label_clusterer = RankedLabelClusterer(text_embedder=text_embedder)

# Audio emotion (REST-hosted endpoint — vedi docs/audio-emotion.md)
# emotion_provider = RestHostedModelProvider(endpoint_url=..., build_request=..., api_key=...)
# audio_emotion = AudioEmotionModel(emotion_provider, "emotion-model-id", ModelOutNormalizer())
```

#### Parametri di generazione LLM

I parametri (`temperature`, `top_p`, `max_tokens`, `reasoning_effort`, `response_format`, ecc.) si impostano **solo alla costruzione** di `LLMModel`, non per singola richiesta. Vengono inoltrati al provider su ogni chiamata.

| Parametro | Default su `LLMModel` | Note |
|-----------|----------------------|------|
| `temperature` | `0.7` | Passa `None` per usare il default del modello remoto |
| `top_p` | `1.0` | Di solito si regola `temperature` **oppure** `top_p` |
| `max_tokens`, `stop`, `seed` | non inviati | Impostali solo se servono |
| `frequency_penalty`, `presence_penalty`, `repetition_penalty` | non inviati | Anti-ripetizione; preferirne uno |
| `reasoning_effort` | non inviato | `"low"` \| `"medium"` \| `"high"` (modelli reasoning) |
| `reasoning_enabled` | non inviato | `True` / `False` per modelli hybrid |
| `response_format` | non inviato | Output strutturato lato **provider** (es. JSON) |
| `extra` | non inviato | Chiavi provider-specific (es. `chat_template_kwargs`) |

`response_format` e `context.metadata["output_schema"]` sono **indipendenti**: il primo guida la generazione API; il secondo valida il risultato in pipeline. Riferimento completo: [LLM generation parameters](llm-generation-params.md).

Esempio produzione con Together:

```python
import os

from ianuacare import LLMModel, ModelOutNormalizer, TogetherAIProvider

together = TogetherAIProvider(
    api_key=os.environ["TOGETHER_API_KEY"],
    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
)

llm = LLMModel(
    together,
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ModelOutNormalizer(),
    temperature=0.2,
    top_p=0.9,
    max_tokens=2048,
    reasoning_effort="medium",
    response_format={"type": "json_object"},
)
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
            "label_clusterer": label_clusterer,
            "ranked_label_clusterer": ranked_label_clusterer,
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
| `"audio_emotion"` | `{"audio_path": "/path/file.wav"}` | `{"arousal": 0.54, "dominance": 0.61, "valence": 0.40}` |
| `"label_clusterer"` | `{"vectors": [[...], [...], ...], "label_clusters": {"my_label": ["anchor1", "anchor2"]}, "texts": ["...", ...]?, "point_ids": [...]?}` | `{"labels": [...], "assigned_labels": [...], "cluster_to_label": {...}, "projected_vectors": [...], "explained_variance_ratio": [...], "texts": [...], "point_ids": [...]}` |
| `"ranked_label_clusterer"` | `{"vectors": [[...], ...], "label_clusters": {"my_label": ["anchor1"]}, "texts": ["...", ...]?, "point_ids": [...]?, "num_clusters": 8}` | `{"labels": [...], "assigned_labels": [...], "cluster_to_label": {...}, "ranked_clusters": [...], "texts": [...], "point_ids": [...]}` |
| `"nlp"` (o altro) | Qualsiasi dizionario | Dipende dal provider configurato |

!!! note "Cosa succede se non passi `model_key`"
    La pipeline usa il `default_model_key` impostato nell'Orchestrator (nel
    setup sopra era `"nlp"`). Se c'e' un solo modello registrato, usa quello.
    Altrimenti alza `OrchestrationError`.

### Esempio: generare un riassunto con LLM

I parametri di generazione (temperature, output format, ecc.) sono gia' configurati su `LLMModel` al setup (sezione 1). La pipeline riceve solo il testo da elaborare.

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

Con validazione output strutturato (schema in pipeline, indipendente da `response_format`):

```python
context = RequestContext(
    user=user,
    product="my-product",
    metadata={
        "model_key": "llm",
        "output_schema": {
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
    },
)
packet = pipeline.run_model({"text": "Testo clinico..."}, context)
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

### Esempio: emotion da audio (REST hosted)

```python
context = RequestContext(
    user=user,
    product="my-product",
    metadata={"model_key": "audio_emotion"},
)
packet = pipeline.run_model(
    {"audio_path": "/path/to/session.wav"},
    context,
)
print(packet.inference_result)
# {"arousal": 0.54, "dominance": 0.61, "valence": 0.40}
```

Vedi [Audio emotion (REST-hosted)](audio-emotion.md) per il wiring di `RestHostedModelProvider`.

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

## 5 — File su bucket (S3): `pipeline.run_bucket(...)` e `run_audio`

Per preparare upload e fare retrieval di riferimenti da DB + object storage, usa
`pipeline.run_bucket(operation, input_data, context, content_type="audio" | "text")`.
Per compatibilità, `pipeline.run_audio(operation, input_data, context)` equivale a
`run_bucket(..., content_type="audio")`.

Questo flusso **non usa l'Orchestrator**, **non esegue inferenza AI** e salva
metadati su DB con chiavi S3 ricostruibili (`.../audio/...` per wav/mp3,
`.../text/...` per `.txt`/`.md`).

### Come chiamarlo

| `operation` | Campi richiesti in `input_data` | Output |
|---|---|---|
| `"prepare_upload"` | `collection`, `filename` (audio: `.wav`/`.mp3`; text: `.txt`/`.md`) | Metadata + `upload_url` presigned PUT |
| `"upload_direct"` | `collection`, `filename`, `content` (bytes/str) **oppure** `content_base64` | Upload oggetto + metadata DB |
| `"retrieve"` | `collection`, `lookup_field`, `lookup_value` | Metadata record + `download_url` presigned GET |

### Regole principali

- Upload single-object: il file viene caricato su S3 intero (no multipart/chunk upload).
- Object key deterministico: `{product}/{user_id}/{audio|text}/{request_id_o_id}.{ext}` (segment in base al `content_type`).
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

Per scrivere, cercare, elencare o cancellare embeddings nel DB vettoriale l'app usa `pipeline.run_vector(operation, input_data, context)`.

| `operation` | Campi richiesti in `input_data` | Output |
|---|---|---|
| `"upsert"` | `collection`, `artefatti`, `vector_field` (`text`/`chunks`/`sentence`/`words`) | conteggio upsert |
| `"search"` | `collection`, `filters.level`, `vector` **oppure** `prompt`, `top_k` opzionale | lista hit |
| `"scroll"` | `collection`; opzionale `filters` (match esatto sul payload), `batch_size`, `with_vectors`, `with_payload` | lista di punti (`id`, payload e/o vector secondo i flag) |
| `"delete"` | `collection`, `ids` **oppure** `filters` | conteggio delete |

### Esempio: upsert

`vector_field` seleziona il livello da indicizzare: un punto per artefatto con `"text"`, un punto per elemento di lista con `"chunks"`, `"sentence"` o `"words"`. Gli artefatti prodotti da `text_embedder` contengono già tutti i livelli (`chunks`/`chunks_vect`, `sentence`/`sentence_vect`, ecc.).

```python
packet = pipeline.run_vector(
    "upsert",
    {
        "collection": "clinical_notes",
        "vector_field": "chunks",  # oppure "text", "sentence", "words"
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

### Esempio: scroll (tutti i punti)

L'operazione `scroll` attraversa tutta la collection usando l'API `scroll` del client Qdrant (paginazione interna con `batch_size`). Non richiede `filters.level`; i filtri opzionali applicano condizioni di uguaglianza sui campi del payload.

```python
packet = pipeline.run_vector(
    "scroll",
    {
        "collection": "clinical_notes",
        "filters": {"level": "sentence"},  # opzionale: limita ai payload che matchano
        "batch_size": 256,
        "with_payload": True,
        "with_vectors": False,
    },
    context,
)
for point in packet.processed_data:
    print(point["id"], point.get("payload"))
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
    Choice -->|"Bucket S3"| RunBucket["run_bucket(op, data, context
    + content_type)
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
| **Bucket S3** | Chiama `run_bucket(op, data, context, content_type=audio|text)` (o `run_audio` per solo audio) | Valida payload, salva metadata DB, upload/download presigned |
| **Vector DB** | Chiama `run_vector(op, data, context)` | Valida payload vector, upsert/search/scroll/delete su vector client |
| **Errori** | Cattura eccezioni e mappa a HTTP status | Alza eccezioni tipizzate |
