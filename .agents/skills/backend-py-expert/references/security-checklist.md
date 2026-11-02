# Security Checklist

Security checklist for backend Python applications, aligned with OWASP Top 10 and Python best practices. Apply these checks to every feature and endpoint.

## OWASP Top 10 — Python Mitigations

### 1. Injection (SQL, NoSQL, Command)

- **Always** use parameterized queries — never concatenate user input into SQL
- Use ORM query builders (SQLAlchemy, Django ORM) that parameterize by default
- For raw queries: use bound parameters, never f-strings or `.format()`
- Validate input with Pydantic before it reaches any query

```python
# GOOD: parameterized (SQLAlchemy)
stmt = select(User).where(User.id == user_id)

# GOOD: parameterized raw SQL
result = await session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

# BAD: f-string interpolation
result = await session.execute(text(f"SELECT * FROM users WHERE id = '{user_id}'"))  # SQL injection
```

### 2. Broken Authentication

- Hash passwords with `passlib` using bcrypt or argon2 (never MD5, SHA-1, or plain SHA-256)
- Cost factor: bcrypt minimum 12 rounds, argon2 with recommended settings
- Implement account lockout after N failed attempts (5-10)
- Use secure session/token storage (HttpOnly, Secure, SameSite cookies)
- Never expose whether an email exists in login error messages

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain, hashed)
```

### 3. Sensitive Data Exposure

- Never log passwords, tokens, API keys, or PII — use Pydantic `SecretStr` for sensitive fields
- Use `HTTPS` everywhere — redirect HTTP to HTTPS
- Encrypt sensitive data at rest (database column encryption for PII)
- Set proper cache headers on sensitive responses (`Cache-Control: no-store`)
- Mask or redact sensitive fields in API responses

```python
from pydantic import BaseModel, SecretStr

class DatabaseSettings(BaseModel):
    """Database configuration with masked password."""

    host: str
    port: int = 5432
    password: SecretStr  # Never logged, repr shows '**********'
```

### 4. XML External Entities (XXE)

- If processing XML: use `defusedxml` instead of stdlib `xml` — it disables entity resolution by default
- Prefer JSON over XML wherever possible
- Never use `pickle.loads()` on untrusted input — use JSON or msgpack

### 5. Broken Access Control

- Implement authorization checks **on every endpoint** — never rely on frontend-only checks
- Use RBAC (Role-Based Access Control) middleware or FastAPI dependencies
- Check resource ownership: user can only access their own resources unless admin
- Return `403 Forbidden` for authorization failures, `401 Unauthorized` for authentication failures

### 6. Security Misconfiguration

- Use security headers middleware (`starlette-security-headers`, Django `SecurityMiddleware`)
- Remove default error pages and stack traces in production
- Set `DEBUG=False` in production (Django), disable `/docs` in production (FastAPI)
- Review and harden framework-specific defaults

### 7. Cross-Site Scripting (XSS)

- Relevant for server-rendered HTML (Django templates, Jinja2) — templates auto-escape by default
- For API-only backends: set `Content-Type: application/json` — browsers won't execute JSON as HTML
- Never reflect user input in error messages without sanitization

### 8. Insecure Deserialization

- Never use `eval()`, `exec()`, or `pickle.loads()` on user input
- Validate all deserialized data with Pydantic models
- Prefer JSON over custom serialization formats
- Never use `yaml.load()` — use `yaml.safe_load()`

### 9. Using Components with Known Vulnerabilities

- Run `pip-audit` or `safety check` regularly (weekly or in CI)
- Pin dependency versions with lockfiles (`uv.lock`, `poetry.lock`, `requirements.txt` with hashes)
- Review and update dependencies on a regular schedule
- Use Dependabot or Renovate for automated vulnerability scanning

### 10. Insufficient Logging & Monitoring

- Log all authentication events (login, logout, failed attempts)
- Log authorization failures
- Log input validation failures with request context (but not the raw input)
- Include correlation/request IDs in all logs
- Set up alerts for anomalous patterns (spike in 401s, 403s, 500s)

## JWT Best Practices

### Token structure

```python
import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived access token.

    Args:
        user_id: The user's unique identifier.
        role: The user's role for RBAC.

    Returns:
        Encoded JWT string.
    """
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.ACCESS_TOKEN_SECRET, algorithm="RS256")


def create_refresh_token(user_id: str, family_id: str) -> str:
    """Create a longer-lived refresh token with family tracking.

    Args:
        user_id: The user's unique identifier.
        family_id: Token family ID for rotation tracking.

    Returns:
        Encoded JWT string.
    """
    payload = {
        "sub": user_id,
        "family": family_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.REFRESH_TOKEN_SECRET, algorithm="RS256")
```

### Rules

- Use **RS256** (asymmetric) over HS256 when multiple services verify tokens
- Access tokens: **15 minutes** max expiry
- Refresh tokens: **7 days** max, with rotation on each use
- Store refresh tokens in database — revoke on logout, password change, suspicious activity
- Implement **token family** tracking to detect stolen refresh tokens
- Never store JWTs in localStorage — use HttpOnly cookies or secure in-memory storage

### Refresh token rotation

1. Client sends expired access token + valid refresh token
2. Server validates refresh token, checks it's not revoked
3. Server issues **new access token AND new refresh token**
4. Server revokes the old refresh token
5. If a revoked refresh token is presented -> revoke entire token family (compromise detected)

## RBAC Dependency (FastAPI)

```python
from fastapi import Depends, HTTPException, status

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Extract and validate the current user from JWT.

    Args:
        token: Bearer token from Authorization header.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.ACCESS_TOKEN_SECRET, algorithms=["RS256"])
        user = await user_repo.find_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def require_role(*allowed_roles: str):
    """Dependency that checks if the user has the required role.

    Args:
        allowed_roles: Roles permitted to access the endpoint.

    Returns:
        FastAPI dependency function.
    """
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return check_role


# Usage
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_role("admin")),
) -> None:
    ...
```

## CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Explicit list, never ["*"] in production
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
    max_age=86400,  # 24 hours preflight cache
)
```

## Input Sanitization

- Trim whitespace on string inputs (Pydantic validators)
- Normalize unicode (NFC) for comparison fields (email, username)
- Reject or sanitize control characters
- Limit string lengths at the schema level (Pydantic `Field(max_length=...)`)
- Limit request body size at the framework level (e.g. 1MB default)

## Rate Limiting

- Apply to all public endpoints, stricter on auth endpoints
- Auth endpoints: 5-10 attempts per minute per IP
- API endpoints: 100-1000 requests per minute per user/API key
- Use Redis for distributed rate limiting across multiple instances

## Dependency Audit Checklist

- [ ] `pip-audit` or `safety check` runs in CI and blocks on high/critical
- [ ] Lockfile is committed and reviewed in PRs (`uv.lock`, `poetry.lock`)
- [ ] Dependabot or Renovate is configured for automated updates
- [ ] No `setup.py` `postinstall` scripts from untrusted packages
- [ ] Review new dependencies before adding (check maintainer, downloads, last update)
