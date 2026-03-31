---
name: spec-driven-planning
description: Plan backend implementation from specs for Flask services and APIs. Use when decomposing a feature into tasks, estimating scope, or creating implementation issues.
---

# Spec-Driven Planning (Backend)

Turn a feature spec into an ordered execution plan.

## Workflow

1. Read spec from `specs/features/<name>.md`.
2. Clarify unknowns (data model, auth scope, API contract, ianua dependency).
3. Split work into atomic tasks (1-3 hours each).
4. Order tasks by dependency and risk.
5. Convert tasks into actionable GitHub issues when requested.

## Suggested task order
1. Domain/data model changes
2. `ianuacare` adapter/integration changes
3. Service/business logic
4. Flask routes + validation + error mapping
5. Tests (unit + integration/API)
6. OpenAPI update
7. Operational changes (Docker/CI/observability)

## Planning checklist
- Clear acceptance criteria per task
- Explicit test strategy per task
- Security/privacy impact noted for healthcare data
- Rollback or mitigation plan for risky changes

## Additional Reference
- See [planning-checklist.md](planning-checklist.md)
