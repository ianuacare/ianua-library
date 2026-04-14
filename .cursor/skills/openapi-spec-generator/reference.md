# OpenAPI Generator Reference

## File Locations

| File | Purpose |
|------|---------|
| `specs/api/openapi.yml` | Root document — info, servers, security, $ref paths |
| `specs/api/paths/<resource>.yml` | Per-resource endpoint definitions |
| `specs/api/schemas/<model>.yml` | Reusable model schemas |
| `specs/api/schemas/error.yml` | Standard error schemas |

## Naming Conventions

| Concept | Convention | Example |
|---------|-----------|---------|
| operationId | camelCase, verb+noun | `listCompiles`, `createPatient` |
| Tag | PascalCase, plural | `Compiles`, `Patients` |
| Schema name | PascalCase | `Compile`, `Patient`, `ValidationError` |
| Path parameter | camelCase | `patientId`, `surveyId` |
| Query parameter | snake_case | `from`, `to`, `page` |

## Authentication

```yaml
# In openapi.yml components:
securitySchemes:
  bearerAuth:
    type: http
    scheme: bearer

# On each operation:
security:
  - bearerAuth: []
```

## Common Parameters

**Pagination** (when endpoint supports Pagy):
```yaml
parameters:
  - name: page
    in: query
    schema:
      type: integer
      minimum: 1
      default: 1
  - name: items
    in: query
    schema:
      type: integer
      minimum: 1
      maximum: 100
      default: 20
```

**Date range filter**:
```yaml
parameters:
  - name: from
    in: query
    schema:
      type: string
      format: date
    description: Start date (inclusive), defaults to 1 month ago
  - name: to
    in: query
    schema:
      type: string
      format: date
    description: End date (inclusive), defaults to tomorrow
```

**ID path parameter**:
```yaml
parameters:
  - name: id
    in: path
    required: true
    schema:
      type: integer
      format: int64
```

## Response Status Codes Reference

| Code | When |
|------|------|
| 200 | GET success, PATCH/PUT success |
| 201 | POST success (resource created) |
| 204 | DELETE success (no body) |
| 400 | Malformed request (invalid date format, etc.) |
| 401 | Missing or invalid Bearer token |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 422 | Validation errors on request body |
| 500 | Internal server error |

## EasyDoctor Domain Schemas

Schemas already defined in `specs/api/schemas/`:
- `error.yml` — `Error`, `ValidationError`
- `compile.yml` — `Compile` (Answer with completed status)

To check if a schema already exists before creating a new one:
```bash
ls specs/api/schemas/
```

## Validation Gem

Add to `Gemfile` (group: development, test):
```ruby
gem "openapi_parser", require: false
```

Rake task example (`lib/tasks/openapi.rake`):
```ruby
namespace :openapi do
  desc "Validate OpenAPI specifications"
  task validate: :environment do
    require "openapi_parser"
    require "yaml"

    spec_file = Rails.root.join("specs/api/openapi.yml")
    spec = YAML.load_file(spec_file)
    OpenAPIParser.parse(spec, strict_reference_validation: true)
    puts "OpenAPI spec is valid!"
  rescue OpenAPIParser::OpenAPIError => e
    puts "OpenAPI validation failed: #{e.message}"
    exit 1
  end
end
```
