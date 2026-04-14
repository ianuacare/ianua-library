# Security Checklist — Reference

This file is loaded on demand when the task involves security-sensitive code. EasyDoctor is a **healthcare platform** — security is non-negotiable.

---

## Authentication

### Devise Configuration

| Module | Purpose |
|---|---|
| `database_authenticatable` | Password-based login |
| `registerable` | Patient self-registration |
| `recoverable` | Password reset |
| `rememberable` | "Remember me" cookies |
| `validatable` | Email/password format validation |
| `invitable` | Doctor/admin invitation workflow |
| `confirmable` | Email confirmation |
| `timeoutable` | Session expiry |
| `two_factorable` | 2FA (custom module) |

**Rules:**
- Never modify Devise modules without Ask First confirmation
- SPID (Italian identity) authenticates via JWT callback at `/auth/callback` — verify JWT signature
- API authentication uses Bearer tokens via `ApiToken` model — never session-based

### API Authentication

```ruby
class Api::ApplicationController < ActionController::Base
  protect_from_forgery with: :null_session

  before_action :authenticate

  private

  def authenticate
    authenticate_with_http_token do |token, _options|
      @api_token = ApiToken.find_by(token:)
    end

    head :unauthorized unless @api_token
  end
end
```

---

## Authorization

### Action Policy Checklist

- [ ] Every backoffice controller has `verify_authorized` (via base controller)
- [ ] Every action calls `authorize!` — collection actions with no record, member actions with `@record`
- [ ] Index actions use `authorized_scope` for scoped queries
- [ ] `pre_check :deny_external_clinicians` on policies where external doctors should be restricted
- [ ] `DepartmentScoped` concern included where department-based access control applies
- [ ] Policies define `relation_scope` for list filtering

### Common Policy Pattern

```ruby
class Backoffice::PathwayPolicy < ApplicationPolicy
  include DepartmentScoped

  pre_check :deny_external_clinicians

  relation_scope do |scope|
    department_scope(scope)
  end

  def index? = manage?
  def show? = manage?
  def create? = manage?
  def update? = manage?
  def destroy? = act_as_admin?
  def duplicate? = manage?
end
```

---

## Data Protection (Healthcare PII)

### What is PII in EasyDoctor

| Field | Classification | Storage |
|---|---|---|
| Email | PII | Encrypted (`encrypts :email, deterministic: true`) |
| Fiscal code | PII | Encrypted |
| Health data (survey answers, vitals) | Sensitive health data | Standard DB (encrypted at rest in production) |
| Name | PII | Standard DB |
| Phone | PII | Standard DB |

### Rules

1. **Never log PII** — no `Rails.logger.info("User: #{user.email}")`. Log user IDs only.
2. **Never expose PII in URLs** — use record IDs, never email or fiscal code in routes
3. **Never return PII in API responses** unless explicitly required by the endpoint contract
4. **Encrypt PII at rest** — use Active Record Encryption for fields queried directly
5. **Minimize PII collection** — don't store what you don't need
6. **Audit trail** — `ApiRequest` logs API access (token, IP, timestamp — not request body with PII)

---

## Input Validation

### Strong Parameters

```ruby
# Always use params.expect (Rails 8 style)
def pathway_params
  params.expect(pathway: [:name, :description, :status, department_ids: []])
end
```

**Rules:**
- Never `permit!` — always list allowed attributes explicitly
- Nested attributes: use `_attributes` suffix with `id` and `_destroy` if applicable
- Array params: `department_ids: []`
- Never pass user-controlled values to `send()`, `constantize`, or `eval()`

### SQL Injection Prevention

```ruby
# CORRECT — parameterized
User.where("email = ?", params[:email])
User.where(email: params[:email])

# NEVER — string interpolation
User.where("email = '#{params[:email]}'")  # SQL INJECTION
```

---

## Webhook Security

```ruby
# Verify webhook signatures before processing
class Webhooks::SurveyjsController < ApplicationController
  skip_before_action :verify_authenticity_token

  def create
    # Verify signature/source before processing
    head :unauthorized unless valid_webhook?
    # Process...
  end
end
```

**Rules:**
- Skip CSRF protection (`verify_authenticity_token`) only for webhook endpoints
- Verify webhook signatures/tokens before processing payload
- Never trust webhook payload without validation
- Log webhook receipt (without PII from payload)

---

## Session Security

- Sessions expire via Devise `timeoutable` module
- CSRF protection enabled by default (never disable for backoffice)
- API controllers use `protect_from_forgery with: :null_session`
- `HttpOnly` and `Secure` flags on cookies (Rails defaults in production)

---

## Dependency Security

```bash
# Run regularly (CI enforces these)
bin/bundler-audit --update    # Gem vulnerability check
bin/brakeman -q -w2           # Static analysis for security issues
bin/importmap audit            # JS dependency audit
```

**Rules:**
- Address critical vulnerabilities immediately
- Update dependencies regularly
- Review Brakeman warnings — false positives should be documented and suppressed with justification
