# Audio transcription and diarization

This page documents the reusable speech pipeline in **`ianuacare.ai.audio`**
(also re-exported from the top-level `ianuacare` package).

The module is designed to be orchestration-friendly from application code while
keeping signal-processing and provider-facing primitives inside the library.

## Install

Install the audio extra:

```bash
pip install -e ".[audio]"
```

Or with development dependencies:

```bash
pip install -e ".[dev,audio]"
```

## Public API

Primary import path:

```python
from ianuacare.ai.audio import (
    DiarizationPipeline,
    NullSpeechTranscriber,
    OpenAISpeechTranscriber,
    SpeechTranscriber,
    SummaryGenerator,
    WhisperTranscriber,
)
```

The same symbols are available from `from ianuacare import ...` for convenience.

- **`SpeechTranscriber`** — protocol for file-based ASR; plug in any backend.
- **`OpenAISpeechTranscriber`** / **`WhisperTranscriber`** (alias) — OpenAI transcription API.
- **`NullSpeechTranscriber`** — no-op ASR for tests or offline pipelines.
- **`DiarizationPipeline`** — orchestrates ASR segments + diarization heuristics.
- **`SummaryGenerator`** — summarization from segment dicts via an injected `AIProvider`.

## Pipeline overview

`DiarizationPipeline` runs these steps:

1. Load audio from a file path and run the injected **`SpeechTranscriber`**.
2. Split / clean segment candidates (`PauseDetector`).
3. Extract lightweight features per segment (`SpectralAnalyzer`).
4. Build embeddings (`SpeakerEmbedder`) and cluster (`SpeakerClusterer`).
5. Return a structured `DiarizationResult` with segment-level metadata.

Inject a real transcriber from application configuration; the default constructor uses
`NullSpeechTranscriber` until you pass an implementation (for example OpenAI).

## Basic usage

```python
from ianuacare.ai.audio import DiarizationPipeline, OpenAISpeechTranscriber

# Example: OpenAI — application supplies the client and model.
transcriber = OpenAISpeechTranscriber(client=my_openai_client, model="whisper-1")
pipeline = DiarizationPipeline(transcriber=transcriber)
result = pipeline.run(
    "/path/to/session.wav",
    num_speakers=2,
    language="it",
)

print(result.raw_transcription)
for segment in result.segments:
    print(segment["speaker_id"], segment["start"], segment["end"], segment["text"])
```

## Summary generation

`SummaryGenerator` expects **segment dictionaries** (e.g. from `DiarizationResult.segments`)
and an optional **`AIProvider`**. For `model_name="summarizer"`, the provider should return
`{"text": "..."}`; otherwise the library falls back to heuristic bullet points.

```python
from ianuacare import AIProvider
from ianuacare.ai.audio import SummaryGenerator

generator = SummaryGenerator(AIProvider(my_infer_fn))
summary = generator.generate(
    segments=[
        {"speaker_id": 0, "text": "Hello."},
        {"speaker_id": 1, "text": "Hi there."},
    ],
    context={"session_id": "ses_1"},
)
print(summary.text)
```

## Configuration guidance

- Keep application secrets (for example API keys) in environment variables.
- Select `num_speakers` from domain context; defaulting to 2 is reasonable for
  one clinician and one patient.
- Prefer lossless or high-quality audio (`wav`, high bitrate `m4a`) to improve
  transcript and clustering quality.

## Error model

The module raises typed exceptions from `ianuacare.core.exceptions`:

- `ValidationError` for malformed inputs or unsupported payloads.
- `InferenceError` for provider/model runtime failures.
- `StorageError` only when used with storage-backed utilities.

Application code should map these exceptions to stable API error codes.

## Security and privacy notes

- Do not log raw audio payloads or full transcripts in plaintext logs.
- Avoid placing PHI in trace/debug metadata fields.
- Apply retention controls in the application layer for audio artifacts.
