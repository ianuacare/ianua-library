---
name: flask-api-testing
description: Create and run API tests for Flask backends using pytest and Flask test client. Use when implementing endpoints, fixing API bugs, or adding regression coverage.
---

# Flask API Testing

Focus on endpoint behavior and contract stability.

## Test strategy
- Use `pytest` with Flask test client fixture
- Cover happy path, validation errors, auth failures, and upstream failures
- Assert status code + JSON body keys/types

## Recommended structure
```python
def test_create_resource_success(client, auth_headers):
    payload = {"name": "example"}
    response = client.post("/api/v1/resources", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.get_json()
    assert "data" in body
```

## For ianua-library flows
- Mock adapter boundary, not internals of endpoint handler
- Add at least one timeout/error-path test
- Verify mapped error code and HTTP status are stable

## Run
```bash
pytest -q
pytest tests/api/ -q
```
