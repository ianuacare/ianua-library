---
name: openapi-spec-generator
description: Generate and update OpenAPI 3.1 specs for Flask endpoints. Use when adding or changing API routes, request payloads, responses, auth, or API documentation.
---

# OpenAPI Spec Generator (Flask)

Keep `specs/api/` aligned with real endpoint behavior.

## Workflow

1. Read endpoint implementation in `app/**/*.py` and route registration.
2. Update path spec in `specs/api/paths/*.yml`.
3. Update schemas in `specs/api/schemas/*.yml`.
4. Register new path refs in `specs/api/openapi.yml`.
5. Validate using the project's OpenAPI validation command.

## Required per endpoint
- HTTP method + path
- Summary and operationId
- Parameters (path/query/header) with types and required flags
- Request body schema (if applicable)
- Responses (`200/201`, `400/401`, `404` where relevant, `422`, `500`)
- Security requirements (bearer token if protected)
- At least one example payload for success and failure

## Good practices
- Prefer `/api/v1/...` for new endpoints
- Reuse shared error schemas
- Keep field names and nullability consistent with runtime payloads

## Additional Reference
- See [reference.md](reference.md)
