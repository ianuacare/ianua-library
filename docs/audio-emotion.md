# Audio emotion: self-hosted WavLM

`AudioEmotionModel` supports a single clip and duration-weighted emotion scores for
one diarized speaker. `SelfHostedAudioEmotionProvider` wraps `RestHostedModelProvider`
using the `wavlm-emotion` server contract. No storage access happens inside the model.

## Server contract

Send `POST /infer` with `Content-Type: application/json` and optional
`Authorization: Bearer <key>`:

```json
{"model": "wavlm-emotion", "payload": {"audio_base64": "<plain base64 audio>"}}
```

Use the alias `wavlm-emotion`, not a Hugging Face repository name. The response is
`{"model": ..., "scores": {"arousal": ..., "dominance": ..., "valence": ...},
"segments": [...], "raw": {...}}`. The provider preserves this envelope; the model
normalizes `scores`. Server errors become `InferenceError` including HTTP status,
`error.code` and `error.message`. Only HTTP 429 is retried (default two retries),
respecting `Retry-After`. Requests in a batch run serially.

The server accepts WAV, FLAC, OGG and MP3, with limits of 20 MiB audio, 28 MiB JSON
body and 300 seconds. The minimum duration is 0.1 seconds. WebM/M4A, URLs, local
paths and data URIs are not accepted on the wire. The provider reads local paths
and encodes bytes without decoding them for single-clip requests.

The checkpoint is `3loi/SER-Odyssey-Baseline-WavLM-Multi-Attributes`.
There is **no validation for Italian**. Scores are model estimates, not clinical
measurements. The server does not diarize: provide the selected speaker's speech.

## Wiring and payloads

```python
from ianuacare import AudioEmotionModel, ModelOutNormalizer, SelfHostedAudioEmotionProvider

provider = SelfHostedAudioEmotionProvider(
    "http://localhost:8000/infer", api_key=None,
    timeout_seconds=600.0, max_retries=2,
)
emotion = AudioEmotionModel(provider, "wavlm-emotion", ModelOutNormalizer())
models = {"audio_emotion": emotion}

single = emotion.run({"audio_path": "/local/clip.wav"})
batch = emotion.run({
    "audio_path": "/local/session.wav",
    "speaker_id": 1,
    "segments": [
        {"start": 0.0, "end": 2.0, "speaker_id": 0},
        {"start": 2.0, "end": 5.0, "speaker_id": 1},
    ],
})
```

Single clips accept `audio_path`, `audio_bytes` or `audio_base64`, without `segments`.
They return only `arousal`, `dominance`, `valence` and need no audio extras.
Custom providers retain the existing pass-through single-clip payload behavior.

Batch requests require `audio_path` or encoded `audio_bytes`, `segments` (a list)
and `speaker_id`. Install `pip install -e ".[audio]"` for lazy librosa/soundfile
slicing. Segments must have finite, ordered, non-overlapping timestamps within the
recording. Speaker IDs are compared exactly. Invalid input or no usable clips
raises `ValidationError`.

Constructor defaults, overridable in each batch payload:

- `min_clip_seconds=1.0`: discard shorter clips (including short split tails).
- `max_clip_seconds=300.0`: split longer segments before inference.
- `merge_consecutive=False`: when enabled, merge only touching consecutive runs of
  the selected speaker; never include gaps or other speakers.

Require `0.1 <= min_clip_seconds <= max_clip_seconds <= 300`. Clips are mono 16 kHz
PCM16 WAV bytes. ADV means are weighted by the actual duration of each retained
clip, excluding skipped audio. `segment_count` counts inferred clips after merging
and splitting, not input diarization segments.

```python
{
    "arousal": 0.41, "dominance": 0.52, "valence": 0.38,
    "mean": {"arousal": 0.41, "dominance": 0.52, "valence": 0.38},
    "per_segment": [{"start": 2.0, "end": 5.0, "duration": 3.0,
                     "scores": {"arousal": 0.41, "dominance": 0.52, "valence": 0.38}}],
    "speaker_id": 1, "segment_count": 1, "skipped": [],
}
```

Skipped entries carry `start`, `end`, `duration` and
`reason="below_min_clip_seconds"`. Provider errors fail the batch rather than
silently averaging partial results. Input/output data parsers support
`model_key="audio_emotion"` and preserve batch details.

## Storage and post-diarization flow

The caller composes the existing pipelines: `run_bucket("retrieve_to_local", ...)`
materializes the audio, `run_crud("read_one", ...)` fetches saved diarization, and
`run_model` receives the resolved audio path and segments. No application wiring
is installed by this library change.

```python
from pathlib import Path

record = pipeline_database.run_bucket(
    "retrieve_to_local",
    {"collection": "audio", "lookup_field": "id", "lookup_value": audio_id},
    context, content_type="audio",
).processed_data
if record is None:
    raise LookupError("Audio record not found")
try:
    diarization = pipeline_database.run_crud(
        "read_one",
        {"collection": "diarizations", "lookup_field": "id", "lookup_value": diarization_id},
        context,
    ).processed_data
    if diarization is None:
        raise LookupError("Diarization record not found")
    context.metadata["model_key"] = "audio_emotion"
    result = pipeline_model.run_model(
        {"audio_path": record["audio_path"], "segments": diarization["segments"], "speaker_id": 1},
        context,
    )
finally:
    Path(record["audio_path"]).unlink(missing_ok=True)
```

`retrieve_to_local` requires `collection`, `lookup_field`, `lookup_value` and accepts
an optional string `local_path`. It returns the metadata record plus an absolute
`audio_path`, or `None` for a missing record. The object must contain bytes and have
an `object_key`. Without a destination it creates a unique temporary file; explicit
destinations must not already exist. The caller owns cleanup, including on model
failure. This is a storage read operation and invokes the storage output parser.

See [Audio diarization](audio-diarization.md) and
[Application integration flow](application-integration-flow.md).
