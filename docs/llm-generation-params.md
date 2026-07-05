# LLM generation parameters

`LLMModel` accepts **construction-time** generation knobs as explicit keyword arguments. They are collected into an internal `params` mapping and forwarded to the registered `AIProvider` on every `run` / `stream` / `arun` / `astream` call. Parameters are **provider-agnostic**: each backend maps the keys it understands and ignores the rest.

Generation parameters are **not** per-request overrides. Set them when you construct `LLMModel` (or optional provider-level defaults on `TogetherAIProvider`).

## Quick example

```python
import os

from ianuacare import LLMModel, ModelOutNormalizer, TogetherAIProvider

provider = TogetherAIProvider(
    api_key=os.environ["TOGETHER_API_KEY"],
    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
)

llm = LLMModel(
    provider,
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ModelOutNormalizer(),
    temperature=0.2,
    top_p=0.9,
    max_tokens=2048,
    reasoning_effort="medium",
    response_format={"type": "json_object"},
)
```

## Parameter reference

| Parameter | Type | Default on `LLMModel` | Sent when | Purpose |
|-----------|------|----------------------|-----------|---------|
| `temperature` | `float` | `0.7` | always (unless set to `None`) | Sampling randomness; lower = more deterministic |
| `top_p` | `float` | `1.0` | always (unless set to `None`) | Nucleus sampling; tune **either** `temperature` or `top_p`, not both aggressively |
| `top_k` | `int` | `None` | only if set | Hard cap on candidate tokens |
| `max_tokens` | `int` | `None` | only if set | Maximum tokens in the response |
| `stop` | `str` or `list[str]` | `None` | only if set | Stop sequences |
| `seed` | `int` | `None` | only if set | Best-effort reproducibility |
| `frequency_penalty` | `float` | `None` | only if set | Penalize repeated tokens proportionally to frequency (typical range −2 … 2) |
| `presence_penalty` | `float` | `None` | only if set | Penalize tokens that already appeared at least once (typical range −2 … 2) |
| `repetition_penalty` | `float` | `None` | only if set | HuggingFace-style repetition control (typical default on backends: `1.0`; try ~`1.1` for loops) |
| `reasoning_effort` | `"low"` \| `"medium"` \| `"high"` | `None` | only if set | Reasoning depth on supported models (e.g. GPT-OSS) |
| `reasoning_enabled` | `bool` | `None` | only if set | Toggle reasoning on hybrid models (`True` / `False`) |
| `response_format` | `dict` | `None` | only if set | Structured output contract for the **provider** (see below) |
| `extra` | `dict` | `None` | only if set | Provider-specific keys spread into the API call |

Pass `temperature=None` and/or `top_p=None` to **omit** the built-in defaults and let the remote model's own `generation_config.json` defaults apply.

Read-only introspection: `llm.params` returns a copy of the collected mapping.

## `response_format` vs `output_schema`

These solve different problems and are **independent**:

| Mechanism | Where set | What it does |
|-----------|-----------|--------------|
| `response_format` | `LLMModel(...)` constructor | Tells the **provider API** to constrain generation (e.g. JSON mode or JSON Schema). Together/OpenAI-compatible: `{"type": "json_object"}` or `{"type": "json_schema", "json_schema": {...}}`. |
| `output_schema` | `RequestContext.metadata["output_schema"]` | Tells the **orchestration output parser** to validate the model result after inference (required fields and top-level property types). Does **not** change the provider request. |

Use both when you want the API to steer output shape **and** post-validate in the pipeline:

```python
from ianuacare import RequestContext, User

llm = LLMModel(
    provider,
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ModelOutNormalizer(),
    temperature=0.1,
    response_format={"type": "json_object"},
)

context = RequestContext(
    User("u1", "clinician", []),
    "my-product",
    metadata={
        "model_key": "llm",
        "output_schema": {
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
        },
    },
)
```

## Provider mapping

### `TogetherAIProvider`

Constructor optional defaults:

```python
TogetherAIProvider(
    api_key="...",
    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    default_params={"temperature": 0.3},  # optional
)
```

Per-call `params` from `LLMModel` override `default_params`.

Mapping in `TogetherAIProvider`:

- **Pass-through** to `chat.completions.create`: `temperature`, `top_p`, `top_k`, `max_tokens`, `stop`, `seed`, `frequency_penalty`, `presence_penalty`, `repetition_penalty`, `response_format`, `reasoning_effort`
- **`reasoning_enabled`** → `reasoning={"enabled": bool}`
- **`extra`** → spread (e.g. `{"chat_template_kwargs": {"thinking": True}}`)

Embeddings (`model_type="embedding"`) ignore generation params.

See [Together AI chat parameters](https://docs.together.ai/docs/inference/chat/parameters) and [reasoning](https://docs.together.ai/docs/inference/chat/reasoning) for model-specific behaviour.

### `RestHostedModelProvider`

When `params` is set, keys are merged into the dict payload before `build_request` (explicit payload keys win). Your `build_request` hook should forward them in the HTTP body.

### `CallableProvider` / `SpeechTranscriptionProvider`

Accept `params` for interface compatibility; they are ignored.

## Penalties: which one to use?

Together documents three overlapping anti-repetition controls. Prefer **one** rather than stacking all of them:

- **`repetition_penalty`** — reduces probability of tokens already seen in prompt + response (good for phrase loops).
- **`frequency_penalty`** — scales with how often a token was repeated in the response.
- **`presence_penalty`** — fires once a token has appeared, encouraging new vocabulary/topics.

For typical clinical extraction / JSON tasks, start with a low `temperature` and only add penalties if you see repetition in production output.

## Chatbot (`ianuacare.core.chatbot`)

`Chatbot` calls `LLMModel.run` / `arun` / `astream` with a messages list. Generation parameters still come from how you constructed `LLMModel`; the chatbot does not override them per turn.

```python
from ianuacare.core.chatbot import Chatbot

chat_llm = LLMModel(provider, model_id, ModelOutNormalizer(), temperature=0.4, top_p=0.95)
bot = Chatbot(reader=reader, writer=writer, llm=chat_llm, collection="docs", filters={"level": "chunks"})
```

## Related

- [API reference — LLMModel / AIProvider](api-reference.md#ai)
- [Application integration flow](application-integration-flow.md) (Italian, end-to-end wiring)
- [Audio transcription and diarization — LLM summaries](audio-diarization.md#llm-text-generation-summaries-and-similar)
- [Extending — custom providers](extending.md#llm-generation-parameters)
