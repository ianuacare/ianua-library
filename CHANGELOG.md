# Changelog

## Unreleased

- **Pipeline / storage**: `PipelineDatabase.run_bucket` / `Pipeline.run_bucket` with `content_type` (`audio` | `text`) generalizes the former audio-only bucket flow; `Pipeline.run_audio` remains a convenience alias for `run_bucket(..., content_type="audio")` (`PipelineDatabase` exposes only `run_bucket`). Bucket audit events are `pipeline_bucket_started` / `pipeline_bucket_completed`. `Writer.write_bucket_*`, `Reader.read_bucket`, `DataValidator.validate_bucket_payload`, and stub presigned URL helpers on `InMemoryBucketClient` support the same contract in tests and production adapters.
- **Storage parsers**: `StorageInputParser` / `StorageOutputParser` now ship concrete behaviors. CRUD: optional caller-supplied `schema` projects records and coerces JSON Schema scalar types (`string` / `integer` / `number` / `boolean`) on `create` / `update`, validating `required` fields. Bucket: when `chunk_size` is set on `upload_direct`, the audio body is split into byte chunks; on `retrieve`, chunked records are recomposed into `content`. Vector: `upsert` artefatti are sanitized by dropping `None`-valued payload attributes; `search` / `scroll` results pass through a normalization that preserves point shape.
- **Storage timestamps**: `Writer.write_create` and `Writer.write_update` now stamp `created_at` and `updated_at` server-side using `utc_now` (ISO-8601 with `Z` suffix); caller-supplied values for these fields are overridden to keep the audit trail authoritative.
- **LLM input parser**: `InputDataParser` exposes a static `build_prompt(text, context, schema, extras)` and uses it from `_parse_llm_input`. With only `text` the prompt stays empty (backward compatible). Adding `context` / `schema` / `prompt_extras` produces a single labelled prompt with `[CONTEXT]`, `[SCHEMA]`, `[<EXTRA>]`, `[QUESTION]` sections; non-string values are JSON-serialized.
- **Pipeline facade deprecation**: `Pipeline` is deprecated in favor of the explicit `PipelineModel` + `PipelineDatabase` pair. Direct construction now emits a `DeprecationWarning`; `create_stack` continues to expose `stack.pipeline_model`, `stack.pipeline_database`, and `stack.pipeline` (suppressed warning) to keep migration friction-free.

## 0.2.0 - 2026-04-14

- Breaking refactor of `ianuacare.ai`:
  - removed legacy modules `ai.base`, `ai.provider`, `ai.nlp`, `ai.audio`, `ai.cv`, `ai.tabular`
  - introduced unified hierarchy under `ai.models.inference`
  - introduced provider contracts under `ai.providers` (`AIProvider`, `CallableProvider`, `TogetherAIProvider`, `SpeechTranscriptionProvider`)
  - introduced single concrete normalizer `ai.models.normalizer.ModelOutNormalizer`
  - introduced parser package `ai.parsers` (`BaseParser`, `PauseParser`, `SpectralParser`)
- Standardized model output as normalized `dict` artifacts consumed by `Orchestrator` / `Pipeline`.
- Updated top-level exports, tests, and documentation for the new API and migration path.
