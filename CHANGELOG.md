# Changelog

## 0.2.0 - 2026-04-14

- Breaking refactor of `ianuacare.ai`:
  - removed legacy modules `ai.base`, `ai.provider`, `ai.nlp`, `ai.audio`, `ai.cv`, `ai.tabular`
  - introduced unified hierarchy under `ai.models.inference`
  - introduced provider contracts under `ai.providers` (`AIProvider`, `CallableProvider`, `TogetherAIProvider`, `SpeechTranscriptionProvider`)
  - introduced single concrete normalizer `ai.models.normalizer.ModelOutNormalizer`
  - introduced parser package `ai.parsers` (`BaseParser`, `PauseParser`, `SpectralParser`)
- Standardized model output as normalized `dict` artifacts consumed by `Orchestrator` / `Pipeline`.
- Updated top-level exports, tests, and documentation for the new API and migration path.
