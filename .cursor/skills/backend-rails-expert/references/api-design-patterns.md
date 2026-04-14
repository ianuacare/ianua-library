# API Design Patterns — Reference

This file is loaded on demand when the task involves API endpoints in `app/controllers/api/`.

---

## API Architecture

EasyDoctor has a JSON API namespace at `/api` with token-based authentication.

```
Api::ApplicationController (base: token auth, null_session, error handling)
  └── Api::CompilesController (GET /api/compiles)
  └── ... (future endpoints)
```

---

## Authentication

```ruby
class Api::ApplicationController < ActionController::Base
  include Api::CommonErrors

  protect_from_forgery with: :null_session
  before_action :authenticate

  private

  def authenticate
    authenticate_with_http_token do |token, _options|
      @api_token = ApiToken.find_by(token:)
      ApiRequest.log_request(@api_token, request) if @api_token
    end

    head :unauthorized unless @api_token
  end
end
```

**Rules:**
- All API endpoints require Bearer token auth
- Token lookup via `ApiToken` model
- Log API requests for audit trail (via `ApiRequest`)
- Use `protect_from_forgery with: :null_session` — no CSRF for API

---

## Response Format

### Jbuilder Views

```ruby
# app/views/api/compiles/index.json.jbuilder
json.array! @answers do |answer|
  json.extract! answer, :id, :created_at, :updated_at
  json.survey_name answer.survey.name
  json.patient do
    json.extract! answer.user, :id, :first_name, :last_name
  end
  json.responses answer.data
end
```

**Rules:**
- Use Jbuilder (`.json.jbuilder`) for JSON responses — it's in the Gemfile
- Never render PII unless the endpoint contract explicitly requires it
- Use `json.extract!` for simple attribute extraction
- Nest related objects with blocks

### Status Codes

| Situation | Status Code |
|---|---|
| Success (list) | `200 OK` |
| Success (create) | `201 Created` |
| Success (no content) | `204 No Content` |
| Invalid params | `400 Bad Request` |
| Missing/invalid token | `401 Unauthorized` |
| Insufficient permissions | `403 Forbidden` |
| Record not found | `404 Not Found` |
| Validation failure | `422 Unprocessable Entity` |
| Server error | `500 Internal Server Error` |

### Error Envelope

```json
{
  "error": {
    "code": "not_found",
    "message": "Pathway not found"
  }
}
```

Use a shared concern for consistent error handling:

```ruby
module Api::CommonErrors
  extend ActiveSupport::Concern

  included do
    rescue_from ActiveRecord::RecordNotFound do |e|
      render json: { error: { code: "not_found", message: e.message } }, status: :not_found
    end

    rescue_from ActionController::ParameterMissing do |e|
      render json: { error: { code: "bad_request", message: e.message } }, status: :bad_request
    end
  end
end
```

---

## OpenAPI Specification

Every API endpoint must have a corresponding entry in `specs/api/openapi.yml`.

```yaml
paths:
  /api/compiles:
    get:
      summary: List completed survey compilations
      security:
        - bearerAuth: []
      parameters:
        - name: from
          in: query
          schema:
            type: string
            format: date
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Compile'
        '401':
          $ref: '#/components/responses/Unauthorized'
```

**Rules:**
- Update OpenAPI spec in the **same PR** as the code change
- Use `$ref` for shared schemas and responses
- Document all parameters, response codes, and schemas
- Use the `openapi-spec-generator` skill for guidance

---

## Pagination (API)

For paginated API endpoints, use Pagy with JSON metadata:

```ruby
def index
  @pagy, @records = pagy(scope)
  response.headers["X-Total-Count"] = @pagy.count.to_s
  response.headers["X-Page"] = @pagy.page.to_s
  response.headers["X-Per-Page"] = @pagy.limit.to_s
end
```

Or include pagination in the response body:

```ruby
json.data do
  json.array! @records do |record|
    json.extract! record, :id, :name
  end
end
json.meta do
  json.total @pagy.count
  json.page @pagy.page
  json.per_page @pagy.limit
  json.pages @pagy.pages
end
```

---

## Versioning

Currently the API is unversioned (`/api/`). If versioning becomes necessary:

1. Propose as an Ask First architectural decision
2. Prefer URL-based versioning (`/api/v2/`)
3. Document in an ADR
