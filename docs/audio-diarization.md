# Audio transcription and diarization

This page documents the speech flow built with:

- `ianuacare.ai.models.inference` (`Transcription`, `DiarizationModel`, `LLMModel`)
- `ianuacare.ai.providers` (`SpeechTranscriptionProvider`, `CallableProvider`)
- `ianuacare.ai.models.normalizer.ModelOutNormalizer`
- `ianuacare.ai.parsers` (`PauseParser`, `spectral_segmenter`, `segment_duration`)

## Install

Install the audio extra (librosa, scikit-learn, OpenAI client):

```bash
pip install -e ".[audio]"
```

Audio is loaded at 16 kHz mono via **librosa**. No PyTorch or Hugging Face token is required for diarization.

Set only the transcription API key:

```bash
export OPENAI_API_KEY=sk-...
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
2. Normalize transcript segments (`PauseParser`; by default **does not** merge short gaps).
3. Detect spectral change-points on the audio file (MFCC cosine distance) and split ASR segments at those boundaries.
4. Apply a duration cap (`max_segment_seconds`) on embedding chunks.
5. Extract speaker embeddings per chunk (`SpeakerEmbedder`: MFCC + delta statistics, L2-normalized).
6. Cluster embeddings (`SpeakerClusterer`: agglomerative clustering; Silhouette to pick `k` when `num_speakers` is omitted).
7. Merge consecutive sub-chunks with the same speaker into output `segments`.
8. Return a dict with `raw_transcription`, `segments`, and `speakers`.

### Tuning parameters

| Field | Default | Purpose |
|-------|---------|---------|
| `merge_transcript_gaps` | `false` | When `true`, merge Whisper segments with gap ≤ 1.5 s (legacy behaviour). |
| `max_segment_seconds` | `30` | Duration cap applied **after** spectral splitting; `0` disables. |
| `use_spectral_split` | `true` | Use MFCC change-point detection to find boundaries; falls back to uniform splitting on error. |
| `spectral_threshold` | `0.35` | Cosine-distance threshold in `[0, 1]`; lower → more cuts, higher → fewer cuts. |
| `spectral_hop_seconds` | `2.0` | Analysis window size for MFCC computation (seconds). |
| `spectral_min_gap_seconds` | `1.5` | Minimum gap between two consecutive spectral boundaries. |

```python
result = model.run({
    "audio_path": "/path/to/session.wav",
    "num_speakers": 2,
    "use_spectral_split": True,
    "spectral_threshold": 0.35,
    "spectral_hop_seconds": 2.0,
    "spectral_min_gap_seconds": 1.5,
    "max_segment_seconds": 30,
})
```

CLI equivalents: `--no-spectral-split`, `--spectral-threshold`, `--spectral-hop-seconds`,
`--spectral-min-gap-seconds`, `--merge-transcript-gaps`, `--max-segment-seconds`.

## Local CLI script

From the repo root (after installing `[audio]` and setting `OPENAI_API_KEY`):

```bash
python scripts/run_diarization.py /path/to/session.wav --num-speakers 2 --language it
```

Prints `validated_data`, `parsed_data`, `inference_result`, and `processed_data` as the backend would see them.

## Basic usage

```python
from ianuacare import DiarizationModel, ModelOutNormalizer, SpeechTranscriptionProvider, Transcription

provider = SpeechTranscriptionProvider(client=my_openai_client, model="whisper-1")
transcription = Transcription(provider, "whisper-1", ModelOutNormalizer())
model = DiarizationModel(transcription=transcription)
result = model.run({
    "audio_path": "/path/to/session.wav",
    "num_speakers": 2,
    "language": "it",
})

print(result["raw_transcription"])
for segment in result["segments"]:
    print(segment["speaker_id"], segment["start"], segment["end"], segment["text"])
```

## Speaker count

- **`num_speakers`**: fixed number of clusters (typical: `2` for clinician + patient).
- **Omit `num_speakers`** or pass an invalid value: `SpeakerClusterer` searches `k` in `[min_speakers, max_speakers]` using the Silhouette score (defaults: 2–6).
- **`min_speakers` / `max_speakers`**: bounds for automatic `k` selection.

```python
result = model.run({
    "audio_path": "/path/to/session.wav",
    "min_speakers": 2,
    "max_speakers": 4,
})
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
- Prefer lossless or high-quality audio (`wav`, high bitrate `m4a`) to improve transcript and embedding quality.
- Segments shorter than ~50 ms are skipped for embedding and inherit the nearest speaker label.
- Long ASR segments are split at spectral change-points before embedding; text is assigned proportionally by word count.
- For conversations with rapid turn-taking, keep `merge_transcript_gaps` at `false` and tune `spectral_threshold` down (e.g. `0.25`).
- Pass `--no-spectral-split` to use uniform time chunking only.

## Error model

The module raises typed exceptions from `ianuacare.core.exceptions`:

- `ValidationError` for malformed inputs or unsupported payloads.
- `InferenceError` for provider/model runtime failures (missing librosa, audio load errors).
- `StorageError` only when used with storage-backed utilities.

Application code should map these exceptions to stable API error codes.

## Security and privacy notes

- Do not log raw audio payloads or full transcripts in plaintext logs.
- Avoid placing PHI in trace/debug metadata fields.
- Apply retention controls in the application layer for audio artifacts.
