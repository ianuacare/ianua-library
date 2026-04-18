# Audio transcription and diarization

This page documents the new speech flow built with:

- `ianuacare.ai.models.inference` (`Transcription`, `DiarizationModel`, `LLMModel`)
- `ianuacare.ai.providers` (`SpeechTranscriptionProvider`, `CallableProvider`)
- `ianuacare.ai.models.normalizer.ModelOutNormalizer`
- `ianuacare.ai.parsers` (`PauseParser`, `SpectralParser`)

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

```python
from ianuacare import (
    DiarizationModel,
    LLMModel,
    ModelOutNormalizer,
    SpeechTranscriptionProvider,
    Transcription,
)
```

## Pipeline overview

`DiarizationModel` runs these steps:

1. Call `Transcription.run(payload)` (`provider.infer` + normalizer).
2. Filter segments (`PauseParser`).
3. Extract features (`SpectralParser`).
4. Build embeddings (`SpeakerEmbedder`) and cluster (`SpeakerClusterer`).
5. Return a dict with `raw_transcription`, `segments`, and `speakers`.

## Basic usage

```python
from ianuacare import DiarizationModel, ModelOutNormalizer, SpeechTranscriptionProvider, Transcription

provider = SpeechTranscriptionProvider(client=my_openai_client, model="whisper-1")
transcription = Transcription(provider, "whisper-1", ModelOutNormalizer())
model = DiarizationModel(transcription=transcription)
result = model.run({"audio_path": "/path/to/session.wav", "num_speakers": 2, "language": "it"})

print(result["raw_transcription"])
for segment in result["segments"]:
    print(segment["speaker_id"], segment["start"], segment["end"], segment["text"])
```

## LLM text generation (summaries and similar)

`LLMModel` passes payloads to the provider and normalizes output through `ModelOutNormalizer` (same `normalize_summary` path as before). When using `Pipeline` + default `InputDataParser`, register the model under `model_key` `"llm"` and supply `validated_data` with at least `text`; the input parser sets `prompt` to an empty string for the application layer to override if needed. To enforce an output contract, pass a JSON schema via `context.metadata["output_schema"]`: the `OutputDataParser` will check required fields and top-level property types before normalization.

```python
from ianuacare import CallableProvider, ModelOutNormalizer, LLMModel

provider = CallableProvider(lambda _m, _p: {"text": "- point A\n- point B"})
summary = LLMModel(provider, "summarizer", ModelOutNormalizer()).run(
    {"prompt": "", "text": "Long transcript or notes to summarize."}
)
print(summary["text"])
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
