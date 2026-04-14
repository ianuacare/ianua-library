# Security Checklist

Security checklist for backend TypeScript applications, aligned with OWASP Top 10 and Node.js best practices. Apply these checks to every feature and endpoint.

## OWASP Top 10 — Node.js Mitigations

### 1. Injection (SQL, NoSQL, Command)

- **Always** use parameterized queries — never concatenate user input into SQL
- Use ORM query builders (Prisma, Drizzle, Knex) that parameterize by default
- For raw queries: use tagged templates or explicit parameter binding
- Validate input with Zod before it reaches any query

```ts
// GOOD: parameterized
const user = await db.select().from(users).where(eq(users.id, userId));

// BAD: string concatenation
const user = await db.execute(`SELECT * FROM users WHERE id = '${userId}'`); // SQL injection
```

### 2. Broken Authentication

- Hash passwords with bcrypt or argon2 (never MD5, SHA-1, or plain SHA-256)
- Cost factor: bcrypt minimum 12 rounds, argon2 with recommended settings
- Implement account lockout after N failed attempts (5-10)
- Use secure session/token storage (HttpOnly, Secure, SameSite cookies)
- Never expose whether an email exists in login error messages

### 3. Sensitive Data Exposure

- Never log passwords, tokens, API keys, or PII
- Use `HTTPS` everywhere — redirect HTTP to HTTPS
- Encrypt sensitive data at rest (database column encryption for PII)
- Set proper cache headers on sensitive responses (`Cache-Control: no-store`)
- Mask or redact sensitive fields in API responses

### 4. XML External Entities (XXE)

- If processing XML: disable external entity resolution
- Prefer JSON over XML wherever possible

### 5. Broken Access Control

- Implement authorization checks **on every endpoint** — never rely on frontend-only checks
- Use RBAC (Role-Based Access Control) middleware
- Check resource ownership: user can only access their own resources unless admin
- Return `403 Forbidden` for authorization failures, `401 Unauthorized` for authentication failures

### 6. Security Misconfiguration

- Use Helmet.js for secure HTTP headers
- Remove default error pages and stack traces in production
- Disable directory listing
- Set `NODE_ENV=production` in production
- Review and harden framework-specific defaults

### 7. Cross-Site Scripting (XSS)

- Relevant for server-rendered HTML — sanitize output with DOMPurify or equivalent
- For API-only backends: set `Content-Type: application/json` — browsers won't execute JSON as HTML
- Never reflect user input in error messages without sanitization

### 8. Insecure Deserialization

- Never use `eval()`, `Function()`, or `vm.runInNewContext()` on user input
- Validate all deserialized data with Zod schemas
- Prefer JSON over custom serialization formats

### 9. Using Components with Known Vulnerabilities

- Run `npm audit` / `pnpm audit` regularly (weekly or in CI)
- Pin dependency versions with lockfiles
- Review and update dependencies on a regular schedule
- Use tools like Snyk or Dependabot for automated vulnerability scanning

### 10. Insufficient Logging & Monitoring

- Log all authentication events (login, logout, failed attempts)
- Log authorization failures
- Log input validation failures with request context (but not the raw input)
- Include correlation/request IDs in all logs
- Set up alerts for anomalous patterns (spike in 401s, 403s, 500s)

## JWT Best Practices

### Token structure

```ts
// Access token: short-lived
const accessToken = jwt.sign(
  { sub: userId, role: userRole },
  ACCESS_TOKEN_SECRET,
  { expiresIn: "15m", algorithm: "RS256" }
);

// Refresh token: longer-lived, stored securely
const refreshToken = jwt.sign(
  { sub: userId, tokenFamily: familyId },
  REFRESH_TOKEN_SECRET,
  { expiresIn: "7d", algorithm: "RS256" }
);
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

## RBAC Middleware

```ts
/**
 * Middleware that checks if the authenticated user has the required role.
 * @param allowedRoles - Roles permitted to access the endpoint
 */
function requireRole(...allowedRoles: Role[]) {
  return (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    if (!req.user) {
      return res.status(401).json({ error: { code: "UNAUTHENTICATED", message: "Authentication required" } });
    }
    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ error: { code: "FORBIDDEN", message: "Insufficient permissions" } });
    }
    next();
  };
}

// Usage
router.delete("/users/:id", requireRole("admin"), deleteUserHandler);
router.get("/users/me", requireRole("admin", "user"), getMeHandler);
```

## Helmet.js Configuration

```ts
import helmet from "helmet";

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'"],
      styleSrc: ["'self'"],
    },
  },
  hsts: { maxAge: 31536000, includeSubDomains: true },
  frameguard: { action: "deny" },
  referrerPolicy: { policy: "strict-origin-when-cross-origin" },
}));
```

## CORS Configuration

```ts
const corsOptions = {
  origin: env.ALLOWED_ORIGINS.split(","), // Explicit whitelist, never "*" in production
  methods: ["GET", "POST", "PUT", "PATCH", "DELETE"],
  allowedHeaders: ["Content-Type", "Authorization"],
  credentials: true,
  maxAge: 86400, // 24 hours preflight cache
};
```

## Input Sanitization

- Trim whitespace on string inputs
- Normalize unicode (NFC) for comparison fields (email, username)
- Reject or sanitize control characters
- Limit string lengths at the schema level (Zod `.max()`)
- Limit request body size at the framework level (e.g. 1MB default)

## Rate Limiting

- Apply to all public endpoints, stricter on auth endpoints
- Auth endpoints: 5-10 attempts per minute per IP
- API endpoints: 100-1000 requests per minute per user/API key
- Use Redis for distributed rate limiting across multiple instances

## Dependency Audit Checklist

- [ ] `npm audit` / `pnpm audit` runs in CI and blocks on high/critical
- [ ] Lockfile is committed and reviewed in PRs
- [ ] Dependabot or Renovate is configured for automated updates
- [ ] No `postinstall` scripts from untrusted packages
- [ ] Review new dependencies before adding (check maintainer, downloads, last update)
