# API Design Patterns

Patterns for designing consistent, maintainable, and well-documented backend APIs. Confirm idioms with the **official docs** of the framework in use.

## REST Naming Conventions

### Resources

- Use **plural nouns**: `/users`, `/orders`, `/products`
- Nested resources for relationships: `/users/:userId/orders`
- Max 2 levels of nesting — beyond that, use top-level with query filters
- No verbs in URLs: `/users/:id/activate` (not `/activateUser`)

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

All error responses use a consistent shape:

```ts
interface ErrorResponse {
  error: {
    code: string;        // Machine-readable: "VALIDATION_ERROR", "NOT_FOUND"
    message: string;     // Human-readable description
    details?: unknown;   // Optional: validation field errors, context
    requestId?: string;  // Correlation ID for debugging
  };
}
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
    "requestId": "req_abc123"
  }
}
```

## Pagination

### Cursor-based (preferred)

Better performance than offset-based for large datasets. Stable under concurrent writes.

```ts
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    hasMore: boolean;
    cursor?: string; // Opaque cursor for next page
  };
}
```

**Request**: `GET /users?limit=20&cursor=eyJpZCI6MTAwfQ`

**Implementation tips**:
- Cursor is an encoded representation of the last item's sort key
- Always sort by a unique, sequential field (e.g. `id`, `createdAt` + `id`)
- Base64-encode cursor to make it opaque to clients

### Offset-based (simple cases)

Acceptable for small datasets or admin interfaces.

```ts
interface OffsetPaginatedResponse<T> {
  data: T[];
  pagination: {
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
  };
}
```

## Rate Limiting

- Apply rate limiting middleware on all public endpoints
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

## Request Validation

Validate at the boundary, before business logic executes.

```ts
// Define schema
const CreateUserSchema = z.object({
  body: z.object({
    email: z.string().email(),
    name: z.string().min(1).max(100),
    role: z.enum(["admin", "user"]).default("user"),
  }),
  params: z.object({}),
  query: z.object({}),
});

// Middleware validates and types the request
// Framework-specific: use the official validation plugin/middleware
```

### Principles

- Validate body, params, query, and headers separately
- Strip unknown properties (Zod `.strict()` or `.strip()`)
- Coerce types where sensible (string -> number for query params)
- Return all validation errors at once, not one at a time

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

- Maintain an OpenAPI 3.x spec as the **source of truth** for the API
- Generate from code annotations or maintain a standalone spec file — pick one approach per project
- Include: all endpoints, request/response schemas, error responses, auth requirements
- Serve the spec at `/docs` or `/api-docs` in non-production environments

## Versioning

- **URL path versioning** (`/v1/users`) for major breaking changes
- Avoid versioning unless necessary — prefer additive, non-breaking changes
- When versioning: support N and N-1 simultaneously, deprecate with timeline

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
