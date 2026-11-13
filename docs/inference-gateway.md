# Inference gateway provider

`InferenceGatewayProvider` calls the HTTP API of `ianua-models_servers`. Model aliases
are resolved by the gateway to EC2, SageMaker or Bedrock. Library needs the gateway
base URL and API key, with no AWS SDK, credentials or provider-specific endpoint URLs.

```python
import os

from ianuacare import InferenceGatewayProvider

provider = InferenceGatewayProvider(
    base_url=os.environ["INFERENCE_GATEWAY_URL"],  # e.g. http://localhost:8010
    api_key=os.environ.get("INFERENCE_GATEWAY_API_KEY"),
    timeout_seconds=600,
    batch_size=32,
    tool_models={"clinical-llm"},  # Only aliases verified to support tools.
)
```

These environment variable names are an application convention, not automatically
loaded configuration. Pass the API key configured as `GATEWAY_API_KEY` on Server.
Use the gateway root URL, without `/infer`. A reverse-proxy path prefix is supported.

## Completed inference

```python
vectors = provider.infer(
    "query-embeddings",
    ["Quali difficoltà sono emerse?"],
    model_type="embedding",
    params={"dimensions": 1024},
)
```

Embedding input may be a string, a list of strings with `model_type="embedding"`,
or an object with `texts`. `infer` splits synchronous embedding requests into ordered
batches and returns `list[list[float]]`, as required by `TextEmbedder`. It checks vector
count, dimensions and finite numeric components. Empty input makes no HTTP request.

For chat, strings and message lists are converted to a `messages` payload. The
`prompt`/`text` object produced by `InputDataParser` is also supported: an assembled
non-empty `prompt` takes precedence over `text`. Explicit payload dictionaries such
as OCR `{"image_b64": ...}` are forwarded. Parameters are sent separately under `params`.

```python
from ianuacare import LLMModel, ModelOutNormalizer, TextEmbedder

embedder = TextEmbedder(provider=provider, model_name="query-embeddings")
llm = LLMModel(
    provider=provider,
    model_name="clinical-llm",
    normalizer=ModelOutNormalizer(),
    temperature=None,
    top_p=None,
    max_tokens=2048,
    additional_model_fields={
        "thinking": {"type": "adaptive"},
    },
)
summary = llm.run("Testo da riassumere")
```

The thinking options above target Sonnet 4.6; adapt them to the selected model.
`additional_model_fields` is optional and is forwarded on both normal and agent calls.
It does not change the existing boolean `reasoning_enabled` or flatten `extra`.

For chat and OCR, the provider returns the full completed response dictionary.
Text normalization remains the responsibility of existing model wrappers. Complete
Converse `message` blocks, reasoning signatures and usage are preserved in the raw
provider result; normalizing a summary does not preserve all those fields.

Parameters are passed through, not silently converted between vendors. Configure the
application according to the selected model and gateway capabilities. The current
Bedrock gateway accepts `max_tokens`, `temperature`, `top_p`, `stop`,
`additional_model_fields` and `response_format`. Library forwards `response_format`
unchanged; Server maps `text` and `json_schema` to Bedrock's native output configuration.
`json_object` is not supported. `reasoning_effort` and `extra` are not automatically
translated. Tools are described below. Native Converse blocks
may also be supplied in `messages` and `tool_config` for a tool-enabled alias.

## Agent tools

Enable tools per alias with `tool_models={"clinical-llm"}`. The default is an empty
set. Text generation alone does not imply tool capability. `supports_tools` indicates
whether any alias is enabled; `supports_tools_for(model_name)` checks the specific
alias. `LLMModel.achat` uses that model-specific check. Other providers retain their
existing `supports_tools` behavior through the base implementation.

For enabled aliases, the provider translates OpenAI-style function definitions and
assistant `tool_calls` to Converse `tool_config`/`toolUse`, and converts tool responses
to `toolResult`. Consecutive results from multiple calls form one user turn. The
gateway's existing `/infer` API is sufficient; no Server changes are needed.

Tool choices supported are `auto`, `required`, or a named function. Availability of
forced tool choices depends on the underlying model. Unsupported choices and strict
schemas are rejected rather than silently relaxed. Function execution stays in Agent
and its registered handlers; neither the provider nor the gateway executes functions.
Install `ianuacare[agent]` for the agent's JSON-schema validation.

Converse tool requests become the agent's `content`, `tool_calls` and `finish_reason`.
`LLMModel.achat`, Agent and Message also carry optional `provider_metadata`, retaining
the original assistant content blocks, including signed reasoning. Persist this field
with the conversation history and pass it back unchanged; do not render it in the UI.
Visible edits or reuse with a different alias are rejected. Do not edit the conversation
prefix or system instructions while retaining signed messages. Start a fresh history
after switching models or changing those instructions. Metadata is excluded from
conversation-summary prompts, and compaction starts a fresh history with a summary.

The provider is stateless: no conversation cache is hidden in it. Server decides which
physical model each alias uses; configure `tool_models` only for aliases whose destination
and tool capability have been verified. Reset conversation history if that destination
changes. See [AWS tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html)
and [conversation blocks](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html).

## Asynchronous SageMaker jobs

```python
reference = provider.submit(
    "transcription",
    {"audio_uri": "s3://audio-bucket/test-recording.wav", "word_timestamps": True},
)
# Persist reference["model"], reference["job_id"] and reference["status"] in Mind.
# Return from the current application task; consult the job in a later task.
```

`submit` makes exactly one request and returns its envelope. A synchronous alias can
also return `status="completed"`. Async aliases normally return `queued` or
`submission_unknown`; the latter must be reconciled without automatically resubmitting.
`submit` does not split embeddings: explicitly prepare endpoint-sized batches in the
application, storing a reference per job.

```python
from ianuacare import GatewayJobPending

job = provider.get_job(reference["model"], reference["job_id"])
if job["status"] == "completed":
    result = provider.get_result(reference["model"], reference["job_id"])

# Or attempt result retrieval directly in a later task:
try:
    result = provider.get_result(reference["model"], reference["job_id"])
except GatewayJobPending as pending:
    reference = pending.job
    # Persist/schedule the next check; do not resubmit the inference.
```

`get_result(..., model_type="embedding")` returns vectors; other results remain
dictionaries. No in-memory job registry, polling loop or automatic retries are used.
The stored model and job ID can be reused by another process/provider instance.
Server-supplied `status_url` is retained for reference but never followed; job URLs
are constructed from the configured base URL and validated identifiers.

If `infer` unexpectedly receives an async response, it raises `GatewayJobPending`
with `.job`, `.job_id`, `.model_name` and `.status`, preventing a job envelope from
being treated as an empty clinical result. The request has already been submitted;
do not call `infer` again to retrieve that result. PipelineModel's generic error
wrapping still applies: async jobs should be orchestrated explicitly by Mind using
`submit` and `get_job`/`get_result`, outside a synchronous pipeline run.

## Async Python, errors and limitations

`ainfer`/`ainfer_stream` inherit the AIProvider thread-backed behavior.
`asubmit`, `aget_job` and `aget_result` also run the HTTP operation in a worker thread.
Python async execution is distinct from SageMaker's durable asynchronous jobs.

The current gateway has no token streaming: `infer_stream` yields the completed text
as one chunk. Pipeline execution remains unchanged; the agent history additionally
preserves optional provider metadata for tool/reasoning turns.

`GatewayHTTPError` extends `InferenceError`, exposing `status_code`, `.code` and
`retry_after` without copying the remote error message. Failed jobs raise an
`InferenceError` with code `gateway_job_failed`. Queued, pending and unknown submission
states raise `GatewayJobPending` when a completed result is requested.

Transport errors expose `gateway_transport_error`; a failed POST can still have been
accepted remotely. The provider never retries it automatically. Invalid JSON/envelopes
are rejected, and redirects are disabled so an API key is not forwarded elsewhere.
The library adds no hard dependency and does not change application configuration.
