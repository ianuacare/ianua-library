# Planning Checklist

Use this checklist when decomposing a feature spec into implementation tasks.

## Pre-Planning Verification

- [ ] Spec exists in `specs/features/` with status `approved`
- [ ] All clarification questions answered
- [ ] No unresolved dependencies on other in-progress features
- [ ] Stakeholder has approved the spec (gdrive_url populated)

## Task Decomposition Checklist

For each task you create, verify:

- [ ] Task is atomic (single concern, single commit)
- [ ] Task is completable in 1-3 hours
- [ ] Task has clear acceptance criteria
- [ ] Task has at least one associated test requirement
- [ ] Task is ordered correctly (no circular dependencies)

## Domain Analysis Prompts

**Domain/Data**
- Are there new entities or schema changes?
- Is backward compatibility required for existing consumers?
- Are there indexing/performance implications?

**Authorization**
- Which roles/scopes can access each endpoint?
- Is tenant/patient-level scoping enforced?

**API Surface**
- Are new endpoints added? → OpenAPI task required
- Are request/response contracts changed? → breaking change assessment

**ianua-library Integration**
- Does this require new/changed `ianuacare` calls?
- Are timeout/retry/fallback expectations explicit?
- Are external errors mapped to stable internal error codes?

**Operations**
- Are Docker/runtime env vars impacted?
- Are CI checks or deployment steps impacted?

**Observability**
- Do we need new logs/metrics/traces for this flow?
- Are sensitive fields redacted in logs?

## Issue Labels Reference

| Label | When to use |
|-------|------------|
| `feature` | New functionality |
| `bug` | Defect fix |
| `refactor` | Code quality improvement |
| `test` | Test-only change |
| `docs` | Documentation only |
| `api` | API endpoints |
| `auth` | Authentication/authorization |
| `core` | Domain/business logic |
| `ianua` | ianua-library integration |
| `infra` | Infrastructure/CI/deploy |
