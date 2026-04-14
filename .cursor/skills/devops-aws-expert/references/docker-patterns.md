# Docker Patterns

Reference for `devops-aws-expert` skill — containerization best practices.

---

## Base Image Selection

| Use case | Recommended base | Why |
|---|---|---|
| Node.js apps | `node:{version}-slim` | Minimal Debian, good compatibility |
| Python apps | `python:{version}-slim` | Minimal Debian |
| Go apps | `scratch` or `distroless` | Static binaries, smallest surface |
| General purpose | `debian:bookworm-slim` | Stable, well-maintained |
| Alpine consideration | `alpine` | Smallest size, but musl libc can cause issues |

**Rules:**
- Always pin exact version tags (e.g., `node:20.11.0-slim`), never use `latest`
- Prefer `-slim` variants over full images
- Use `distroless` for production when possible (no shell = smaller attack surface)

---

## Multi-Stage Builds

```dockerfile
# Stage 1: Dependencies
FROM node:20.11.0-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Stage 2: Build
FROM node:20.11.0-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 3: Production
FROM node:20.11.0-slim AS production
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1) })"
CMD ["node", "dist/main.js"]
```

**Key principles:**
- Separate dependency installation from code copy (layer caching)
- Copy only production dependencies to final stage
- Run as non-root user
- Include HEALTHCHECK instruction
- Use `.dockerignore` to exclude `node_modules`, `.git`, `*.md`, tests

---

## Layer Caching Optimization

Order Dockerfile instructions from least to most frequently changing:

1. Base image and system packages (rarely changes)
2. Package manager files (`package.json`, `requirements.txt`)
3. Dependency installation (`npm ci`, `pip install`)
4. Application source code (changes frequently)
5. Build step

**Cache-busting anti-patterns to avoid:**
- Copying all files before `npm ci` — invalidates cache on any code change
- Using `ADD` instead of `COPY` (ADD has extra features that can break caching)
- Running `apt-get update` without `apt-get install` in the same `RUN`

---

## Container Security

- **Non-root user**: always create and switch to a non-root user
- **Read-only filesystem**: use `--read-only` flag, mount writable volumes only where needed
- **No secrets in images**: use build args for build-time secrets, env vars for runtime
- **Scan images**: integrate `trivy` or `grype` in CI pipeline
- **Minimal packages**: don't install `curl`, `wget`, etc. in production images unless needed for health checks

```dockerfile
# Security-hardened production stage
FROM gcr.io/distroless/nodejs20-debian12 AS production
COPY --from=build /app/dist /app/dist
COPY --from=deps /app/node_modules /app/node_modules
WORKDIR /app
USER nonroot
CMD ["dist/main.js"]
```

---

## Docker Compose for Local Development

```yaml
version: "3.8"

services:
  app:
    build:
      context: .
      target: build  # Use build stage for dev (includes devDependencies)
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://app:secret@db:5432/appdb
      - REDIS_URL=redis://redis:6379
    volumes:
      - .:/app
      - /app/node_modules  # Anonymous volume to preserve container's node_modules
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: appdb
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

**Guidelines:**
- Use `depends_on` with `condition: service_healthy` for startup ordering
- Mount source code for hot reload in development
- Use named volumes for persistent data
- Keep `docker-compose.yml` for dev, `docker-compose.prod.yml` for production overrides

---

## ECR Lifecycle Policies

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 10 tagged images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["v"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {
        "type": "expire"
      }
    },
    {
      "rulePriority": 2,
      "description": "Expire untagged images older than 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
```

---

## Health Checks and Signal Handling

**Health check endpoint requirements:**
- Return 200 when ready to serve traffic
- Check downstream dependencies (DB, Redis) with timeouts
- Separate liveness (`/healthz`) from readiness (`/ready`) when using orchestrators

**Graceful shutdown:**
- Handle `SIGTERM` signal (sent by ECS/Docker on stop)
- Stop accepting new connections
- Complete in-flight requests (with timeout)
- Close database connections
- Exit with code 0

```javascript
process.on('SIGTERM', async () => {
  server.close();
  await db.disconnect();
  process.exit(0);
});
```

---

## Image Tagging Strategy

- **Production**: tag with git SHA and semantic version (`v1.2.3`, `abc1234`)
- **Staging**: tag with git SHA and `staging-{date}`
- **Never use `latest`** for deployments — it's ambiguous and not rollback-friendly
- **Immutable tags**: enable in ECR to prevent tag overwrites in production
