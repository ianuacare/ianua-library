---
name: spec-driven-planning
description: >-
  Plan feature implementation from technical specs in the /specs folder.
  Use when starting a new feature, creating implementation plans from a spec,
  decomposing requirements into atomic tasks, or creating GitHub issues from specs.
  Activated when the user mentions planning, specs, features, or new GitHub issues.
---

# Spec-Driven Planning

Decomposes a feature spec into an ordered, atomic implementation plan with GitHub issues.

## Workflow

### Step 1 — Load the Spec
Read the feature spec from `specs/features/<name>.md`.
If the spec doesn't exist yet, guide the user to create one using `specs/templates/feature-spec-template.md`.

### Step 2 — Analyze Scope
Identify all affected areas:
- **Models**: new models, new fields/associations, migrations needed
- **Services**: new `ApplicationService` subclasses
- **Policies**: new or updated `ApplicationPolicy` subclasses
- **Controllers**: backoffice and/or API endpoints
- **Views**: Slim templates, ViewComponents
- **Jobs**: background processing requirements
- **Tests**: request specs, model specs, service specs, system specs

### Step 3 — Clarification Loop
Before decomposing, ask targeted questions (max 3-4 at a time):
- "Questa feature richiede nuove tabelle o solo nuovi campi su modelli esistenti?"
- "Quali ruoli devono accedere a questa funzionalita (admin, medico, paziente, agenzia)?"
- "Ci sono dipendenze da altre features in sviluppo?"
- "La feature espone nuovi endpoint API? Se si, serve la spec OpenAPI."
- "Ci sono requisiti di i18n oltre it/en?"
- "Sono richiesti job in background o ricorrenti?"

Iterate until scope is clear. Update the spec if clarifications reveal new requirements.

### Step 4 — Decompose into Tasks
Create atomic tasks following this implementation order:

```
1. Migration (if new table/columns)
2. Model (validations, associations, scopes)
3. Service objects (business logic)
4. Policy (authorization rules)
5. Controller + routes
6. ViewComponents
7. Slim templates
8. Background jobs
9. Unit tests (models, services, policies)
10. Request/integration tests
11. System/E2E tests
12. OpenAPI spec (if API endpoint)
13. i18n keys
```

Each task must be:
- Completable in 1-3 hours
- Independently testable
- Described with clear acceptance criteria

### Step 5 — Create GitHub Issues
For each task, create a GitHub issue:

```bash
gh issue create \
  --title "[feat] <task description>" \
  --label "feature,<domain>" \
  --milestone "<sprint>" \
  --body "$(cat <<'EOF'
## Context
Spec: specs/features/<name>.md

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests passing with >80% coverage

## Technical Notes
- Models: ...
- Migration: yes/no
- Breaking changes: yes/no
EOF
)"
```

Domain labels: `pathways`, `surveys`, `patients`, `api`, `auth`, `admin`, `jobs`

### Step 6 — Output Summary
Present the implementation plan as an ordered checklist with:
- Issue numbers
- Estimated complexity (S/M/L)
- Dependencies between tasks

## Reference Files
- Spec template: [specs/templates/feature-spec-template.md](../../../specs/templates/feature-spec-template.md)
- Planning checklist: [planning-checklist.md](planning-checklist.md)
