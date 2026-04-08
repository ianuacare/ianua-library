# Audio transcription and diarization

This page documents the reusable audio module shipped in `ianuacare.audio`.
The module is designed to be orchestration-friendly from application code while
keeping the signal-processing and LLM primitives inside the library.

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

Available imports from `ianuacare`:

- `WhisperTranscriber`
- `PauseDetector`
- `SpectralAnalyzer`
- `SpeakerEmbedder`
- `SpeakerClusterer`
- `DiarizationPipeline`
- `DiarizationResult`
- `SummaryGenerator`

## Pipeline overview

`DiarizationPipeline` runs these steps:

1. Load audio signal and normalize metadata (sample rate/channels).
2. Detect speech intervals and split candidate segments.
3. Generate transcript chunks with `WhisperTranscriber`.
4. Extract spectral features (`SpectralAnalyzer`) per segment.
5. Build speaker embeddings (`SpeakerEmbedder`).
6. Assign speaker labels with nearest-neighbor clustering (`SpeakerClusterer`).
7. Return a structured `DiarizationResult` with segment-level metadata.

The pipeline output is deterministic for the same input and config, except for
external model variability from upstream providers.

## Basic usage

```python
from ianuacare import DiarizationPipeline

pipeline = DiarizationPipeline()
result = pipeline.run(
    audio_bytes=my_audio_bytes,
    filename="session.wav",
    num_speakers=2,
    language="it",
)

print(result.text)
for segment in result.segments:
    print(segment["speaker"], segment["start"], segment["end"], segment["text"])
```

## Summary generation

Use `SummaryGenerator` on transcript text or already diarized output:

```python
from ianuacare import AIProvider, SummaryGenerator

generator = SummaryGenerator(AIProvider())
summary = generator.generate(
    text="Speaker A: ...\nSpeaker B: ...",
    prompt_template="Generate a concise clinical summary with key points.",
)
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

