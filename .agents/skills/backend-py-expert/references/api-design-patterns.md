# API Design Patterns

Patterns for designing consistent, maintainable, and well-documented backend APIs in Python. Confirm idioms with the **official docs** of the framework in use.

## REST Naming Conventions

### Resources

- Use **plural nouns**: `/users`, `/orders`, `/products`
- Nested resources for relationships: `/users/{user_id}/orders`
- Max 2 levels of nesting — beyond that, use top-level with query filters
- No verbs in URLs: `/users/{id}/activate` (not `/activateUser`)

### HTTP Methods

| Method | Purpose | Idempotent | Response |
|--------|---------|------------|----------|
| GET | Read resource(s) | Yes | 200 with body |
| POST | Create resource | No | 201 with body + Location header |
| PUT | Full replace | Yes | 200 with body |
| PATCH | Partial update | No* | 200 with body |
| DELETE | Remove resource | Yes | 204 no body |

*PATCH can be made idempotent with proper implementation.

### Status Codes

Use the right code for the right situation:

- `200` — success with body
- `201` — created (POST success)
- `204` — success, no body (DELETE)
- `400` — bad request (validation error)
- `401` — unauthenticated (no valid credentials)
- `403` — forbidden (authenticated but not authorized)
- `404` — not found
- `409` — conflict (duplicate resource, state conflict)
- `422` — unprocessable entity (valid syntax but semantic error)
- `429` — too many requests (rate limited)
- `500` — internal server error (never leak stack traces)

## Error Envelope

All error responses use a consistent Pydantic model:

```python
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    """Structured error response."""

    code: str          # Machine-readable: "VALIDATION_ERROR", "NOT_FOUND"
    message: str       # Human-readable description
    details: object | None = None   # Optional: validation field errors, context
    request_id: str | None = None   # Correlation ID for debugging


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: ErrorDetail
```

### Validation error details

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "message": "Invalid email format" },
      { "field": "name", "message": "Must be at least 1 character" }
    ],
    "request_id": "req_abc123"
  }
}
```

## Pagination

### Cursor-based (preferred)

Better performance than offset-based for large datasets. Stable under concurrent writes.

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class PaginationMeta(BaseModel):
    """Cursor-based pagination metadata."""

    has_more: bool
    cursor: str | None = None  # Opaque cursor for next page


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    data: list[T]
    pagination: PaginationMeta
```

**Request**: `GET /users?limit=20&cursor=eyJpZCI6MTAwfQ`

**Implementation tips**:
- Cursor is an encoded representation of the last item's sort key
- Always sort by a unique, sequential field (e.g. `id`, `created_at` + `id`)
- Base64-encode cursor to make it opaque to clients

### Offset-based (simple cases)

Acceptable for small datasets or admin interfaces.

```python
class OffsetPaginationMeta(BaseModel):
    """Offset-based pagination metadata."""

    total: int
    page: int
    page_size: int
    total_pages: int


class OffsetPaginatedResponse(BaseModel, Generic[T]):
    """Offset-paginated list response."""

    data: list[T]
    pagination: OffsetPaginationMeta
```

## Rate Limiting

- Apply rate limiting middleware on all public endpoints
- FastAPI: use `slowapi` (built on `limits` library)
- Django REST Framework: built-in throttling classes
- Use sliding window algorithm (Redis-backed for distributed systems)
- Return rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1620000000
```

- Return `429 Too Many Requests` with `Retry-After` header when exceeded
- Different limits for authenticated vs unauthenticated requests
- Consider per-endpoint limits for expensive operations

### FastAPI with slowapi

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/users")
@limiter.limit("100/minute")
async def list_users(request: Request) -> PaginatedResponse[UserResponse]:
    ...
```

## Request Validation

FastAPI provides native request validation via Pydantic — use it as the primary validation layer.

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    """Request body for creating a user."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(default="user", pattern=r"^(admin|user|viewer)$")


@router.post("/users", status_code=201)
async def create_user(body: CreateUserRequest) -> UserResponse:
    """Create a new user.

    Args:
        body: Validated user creation input.

    Returns:
        The created user.
    """
    ...
```

### Principles

- Validate body, path params, query params, and headers separately
- Use Pydantic `model_config = {"extra": "forbid"}` to reject unknown fields
- Coerce types where sensible (string -> int for query params via `Query`)
- Return all validation errors at once, not one at a time (Pydantic does this by default)

## Idempotency Keys

For mutating operations (POST, non-idempotent PATCH), accept an idempotency key to prevent duplicate processing.

```
POST /orders
Idempotency-Key: idk_abc123def456
```

### Implementation

- Client sends `Idempotency-Key` header
- Server checks if key exists in store (Redis with TTL)
- If exists: return the stored response (same status, same body)
- If not: process request, store response with key, return response
- TTL: 24-48 hours

## OpenAPI / Swagger

- FastAPI **auto-generates** OpenAPI 3.x from route definitions and Pydantic models
- Django REST Framework: use `drf-spectacular` for OpenAPI generation
- Flask: use `flask-smorest` or `apispec`
- Include: all endpoints, request/response schemas, error responses, auth requirements
- Serve the spec at `/docs` (Swagger UI) and `/redoc` (ReDoc) in non-production environments

### FastAPI OpenAPI customization

```python
app = FastAPI(
    title="My Service API",
    version="1.0.0",
    description="Backend API for managing users and orders.",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)
```

## Versioning

- **URL path versioning** (`/v1/users`) for major breaking changes
- Avoid versioning unless necessary — prefer additive, non-breaking changes
- When versioning: support N and N-1 simultaneously, deprecate with timeline

## ASGI vs WSGI

| Feature | ASGI | WSGI |
|---|---|---|
| Async support | Native | No (requires workarounds) |
| Frameworks | FastAPI, Litestar, Starlette | Django, Flask |
| Server | Uvicorn, Hypercorn | Gunicorn, uWSGI |
| WebSockets | Native | Not supported |
| Use when | Async I/O, WebSockets, SSE | Sync-first, Django ecosystem |

- Django can run on ASGI for async views (`uvicorn myproject.asgi:application`)
- Flask has experimental async support but WSGI remains primary

## Content Negotiation

- Default to `application/json`
- Set `Content-Type` header explicitly on all responses
- Accept `application/json` on request bodies; reject others with `415 Unsupported Media Type`

## HATEOAS (when appropriate)

For public APIs where discoverability matters:

```json
{
  "data": { "id": "usr_123", "name": "Alice" },
  "links": {
    "self": "/users/usr_123",
    "orders": "/users/usr_123/orders"
  }
}
```

Not required for internal APIs or BFF (Backend-for-Frontend) services.
