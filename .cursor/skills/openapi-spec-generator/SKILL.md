---
name: openapi-spec-generator
description: >-
  Generate and validate OpenAPI 3.1 specifications for API endpoints in EasyDoctor.
  Use when creating new API endpoints, updating existing ones, documenting the API,
  or when asked to write an OpenAPI spec, Swagger spec, or API documentation.
  Every endpoint in app/controllers/api/ must have a spec in specs/api/.
---

# OpenAPI Spec Generator

Generates and maintains OpenAPI 3.1 specs for every API endpoint.

## Workflow

### Step 1 — Scan the Endpoint
Read:
- Controller: `app/controllers/api/<resource>_controller.rb`
- Routes: relevant section in `config/routes.rb`
- Model: the primary model being serialized
- Request spec: `spec/requests/api/<resource>_spec.rb` (for examples)

### Step 2 — Generate Path Spec

Create `specs/api/paths/<resource>.yml` following the template.
See `specs/templates/api-spec-template.md` for the full YAML template.

Key requirements:
- Every action gets its own operationId (camelCase: `listCompiles`, `createPatient`)
- All parameters documented with type, required flag, and description
- All response codes: 200/201, 401, 422, 500 (add 404 for member actions)
- At least one example per response
- Bearer auth on every operation

### Step 3 — Generate/Update Schemas

For each model serialized in responses, ensure a schema exists in `specs/api/schemas/<model>.yml`.

**Ruby → OpenAPI Type Mapping**:

| Ruby/Rails | OpenAPI type | format |
|-----------|-------------|--------|
| `string` | `string` | — |
| `text` | `string` | — |
| `integer` | `integer` | `int64` |
| `float`/`decimal` | `number` | `float` |
| `boolean` | `boolean` | — |
| `date` | `string` | `date` |
| `datetime`/`timestamp` | `string` | `date-time` |
| `json`/`jsonb` | `object` | — |
| enum | `string` | + `enum: [values]` |
| belongs_to (FK) | `integer` | — |
| has_many | `array` | + `items: $ref` |

**Nullable fields**: add `nullable: true` for columns that allow NULL.
**Required fields**: include in `required:` array only non-nullable fields without defaults.

### Step 4 — Register in Root Document

Add the path reference to `specs/api/openapi.yml`:

```yaml
paths:
  /compiles:
    $ref: "./paths/compiles.yml#/compiles"
  /new-resource:
    $ref: "./paths/new-resource.yml#/new_resource"
```

Add any new tags to the `tags:` section.

### Step 5 — Validate

```bash
bundle exec rake openapi:validate
```

If the rake task doesn't exist yet, validate manually with:
```bash
# Install openapi_parser if not present
gem install openapi_parser

# Validate
ruby -e "require 'openapi_parser'; OpenAPIParser.parse(YAML.load_file('specs/api/openapi.yml'), strict_reference_validation: true)"
```

## Authentication Pattern

All EasyDoctor API endpoints use Bearer token auth (ApiToken model):

```yaml
security:
  - bearerAuth: []
```

The `bearerAuth` scheme is defined in `specs/api/openapi.yml` components.

## Standard Error Responses

Always use `$ref` to shared error schemas:

```yaml
"401":
  description: Missing or invalid Bearer token
  content:
    application/json:
      schema:
        $ref: "../schemas/error.yml#/Error"
      example:
        code: "bad_credentials"
"422":
  description: Validation errors
  content:
    application/json:
      schema:
        $ref: "../schemas/error.yml#/ValidationError"
```

## Reference Files

- Root spec: [specs/api/openapi.yml](../../../specs/api/openapi.yml)
- Error schemas: [specs/api/schemas/error.yml](../../../specs/api/schemas/error.yml)
- Template: [specs/templates/api-spec-template.md](../../../specs/templates/api-spec-template.md)
- Type mapping reference: [reference.md](reference.md)
