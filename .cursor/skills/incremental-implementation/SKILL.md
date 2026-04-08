---
name: incremental-implementation
description: Implement backend features incrementally with Flask and pytest using a Red-Green-Refactor loop. Use when coding a feature, endpoint, service, or bugfix in the Python backend.
---

# Incremental Implementation (Flask)

Implement one small slice at a time: failing test, minimal code, refactor.

## Cycle

### 1) Branch and scope
- Work in a focused branch (`feat/<issue>-<desc>` or `fix/<issue>-<desc>`)
- Keep each increment small and independently testable

### 2) Red (failing test first)
- Write or extend pytest tests for the target behavior
- Prefer API integration tests for route behavior and unit tests for service logic
- Run only impacted tests first

### 3) Green (minimal implementation)
- Keep Flask routes thin: validation + service call + response mapping
- Put domain logic in service/module layer
- Wrap direct `ianuacare` calls in adapters and map exceptions to app errors

### 4) Refactor
- Remove duplication
- Improve naming and module boundaries
- Keep tests green throughout

### 5) Validate locally
```bash
pytest -q
ruff check .
ruff format --check .
```

Optional (if configured):
```bash
mypy app/
pip-audit
```

## Increment Size Rules
- Target <= 250 lines of non-test code per increment
- One behavior/change objective per commit
- If scope grows, split into a follow-up increment
