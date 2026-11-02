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

**Database**
- Does this require a new table? → Migration task first
- Does this add columns to existing tables? → Migration + Model update
- Does this change indexes? → Performance implications

**Authorization**
- Which roles can perform each action?
- Are there department-scoped restrictions?
- Are external clinicians excluded?

**API Surface**
- Does this create new API endpoints? → OpenAPI spec task required
- Does this change response formats? → Breaking change? → Version bump

**Background Processing**
- Does this need async processing? → Job task
- Is it recurring? → Update `config/recurring.yml`
- Does it send emails? → Mailer + template tasks

**Frontend**
- Does this need new Stimulus controllers?
- Are Turbo Frames needed for partial updates?
- Are new ViewComponents needed?

**Internationalization**
- New user-facing strings? → i18n task for both `it` and `en`
- Date/time formatting? → Use Rails i18n helpers

## Issue Labels Reference

| Label | When to use |
|-------|------------|
| `feature` | New functionality |
| `bug` | Defect fix |
| `refactor` | Code quality improvement |
| `test` | Test-only change |
| `docs` | Documentation only |
| `pathways` | Pathway/Step domain |
| `surveys` | Survey/Answer domain |
| `patients` | Patient management |
| `api` | API endpoints |
| `auth` | Authentication/authorization |
| `admin` | Backoffice admin |
| `jobs` | Background jobs |
| `infra` | Infrastructure/CI/deploy |
