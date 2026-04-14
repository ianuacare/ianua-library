# Observability Patterns

Patterns for structured logging, health checks, tracing, and monitoring in backend TypeScript services. Confirm framework-specific integrations with the **official docs**.

## Structured Logging with Pino

### Setup

```ts
import pino from "pino";

/**
 * Creates the application logger with environment-appropriate configuration.
 */
export function createLogger(env: "production" | "development" | "test") {
  return pino({
    level: env === "test" ? "silent" : env === "production" ? "info" : "debug",
    transport: env === "development"
      ? { target: "pino-pretty", options: { colorize: true } }
      : undefined,
    redact: {
      paths: ["req.headers.authorization", "req.headers.cookie", "*.password", "*.token"],
      censor: "[REDACTED]",
    },
    serializers: {
      err: pino.stdSerializers.err,
      req: pino.stdSerializers.req,
      res: pino.stdSerializers.res,
    },
  });
}
```

### Child loggers

Create child loggers with request context for automatic correlation.

```ts
/**
 * Request logging middleware. Creates a child logger with request ID
 * and attaches it to the request object.
 */
function requestLoggerMiddleware(request: Request, reply: Reply, next: NextFunction) {
  const requestId = request.headers["x-request-id"]?.toString() ?? crypto.randomUUID();

  request.log = logger.child({
    requestId,
    method: request.method,
    url: request.url,
    userAgent: request.headers["user-agent"],
  });

  reply.header("x-request-id", requestId);

  const start = Date.now();
  reply.on("finish", () => {
    const duration = Date.now() - start;
    request.log.info({ statusCode: reply.statusCode, duration }, "Request completed");
  });

  next();
}
```

### Log levels

Use appropriate levels consistently:

| Level | Use for |
|-------|---------|
| `fatal` | Application is about to crash — unrecoverable |
| `error` | Operation failed — requires attention, but app continues |
| `warn` | Something unexpected but handled — degraded behavior |
| `info` | Significant business events — request completed, user created, payment processed |
| `debug` | Detailed diagnostic info — query results, intermediate state |
| `trace` | Very fine-grained — individual function calls (rarely used in production) |

### Logging guidelines

- **Do** log: request start/end, business events, errors with context, external service calls
- **Don't** log: sensitive data (passwords, tokens, PII), large payloads, every function call
- **Always** include: `requestId`, relevant entity IDs, operation name
- **Never** use `console.log` — always use the structured logger

```ts
// GOOD
logger.info({ userId: user.id, orderId: order.id }, "Order created successfully");
logger.warn({ userId: user.id, attempts: failedAttempts }, "Multiple failed login attempts");
logger.error({ err: error, orderId }, "Failed to process payment");

// BAD
console.log("User created"); // No structure, no context
logger.info("Order created for user " + userId); // String concatenation, no structured fields
logger.error(error); // Missing context
```

## Correlation IDs

Propagate a unique ID through the entire request lifecycle for distributed tracing.

### Implementation

1. Extract or generate `requestId` at the entry point (middleware)
2. Attach to the child logger (automatic in Pino child)
3. Pass through to external service calls via headers (`x-request-id`)
4. Include in error responses for client-side debugging
5. Include in queue messages for async operation tracing

```ts
// When calling external services
async function callPaymentService(orderId: string, requestId: string) {
  return fetch("https://payments.internal/charge", {
    headers: {
      "Content-Type": "application/json",
      "x-request-id": requestId, // Propagate correlation ID
    },
    body: JSON.stringify({ orderId }),
  });
}
```

## Health Check Endpoints

### Liveness — `/health`

"Is the process running?" Used by orchestrators (Kubernetes, Docker) to restart crashed instances.

```ts
/**
 * Liveness probe. Returns 200 if the process is running.
 * Does NOT check external dependencies.
 */
app.get("/health", async (request, reply) => {
  return reply.status(200).send({ status: "ok" });
});
```

### Readiness — `/ready`

"Can this instance serve traffic?" Used by load balancers to route traffic.

```ts
/**
 * Readiness probe. Returns 200 if the service can accept requests.
 * Checks database connectivity and other critical dependencies.
 */
app.get("/ready", async (request, reply) => {
  const checks: Record<string, "ok" | "failing"> = {};

  try {
    await db.execute(sql`SELECT 1`);
    checks.database = "ok";
  } catch {
    checks.database = "failing";
  }

  try {
    await redis.ping();
    checks.cache = "ok";
  } catch {
    checks.cache = "failing";
  }

  const allOk = Object.values(checks).every((v) => v === "ok");
  const statusCode = allOk ? 200 : 503;

  return reply.status(statusCode).send({ status: allOk ? "ready" : "not_ready", checks });
});
```

### Guidelines

- Health endpoints should **not** require authentication
- Keep checks fast — timeout after 2-3 seconds
- Don't expose internal details (versions, hostnames) in production
- Separate liveness from readiness — they serve different purposes

## OpenTelemetry

For distributed tracing across multiple services.

### Setup

```ts
import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

/**
 * Initializes OpenTelemetry SDK with auto-instrumentation.
 * Must be called before any other imports.
 */
export function initTelemetry(serviceName: string) {
  const sdk = new NodeSDK({
    serviceName,
    traceExporter: new OTLPTraceExporter({
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://localhost:4318/v1/traces",
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        "@opentelemetry/instrumentation-fs": { enabled: false }, // Too noisy
      }),
    ],
  });

  sdk.start();

  process.on("SIGTERM", async () => {
    await sdk.shutdown();
  });

  return sdk;
}
```

### Custom spans

```ts
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("order-service");

/**
 * Processes an order with tracing for performance visibility.
 */
async function processOrder(orderId: string): Promise<void> {
  return tracer.startActiveSpan("processOrder", async (span) => {
    try {
      span.setAttribute("order.id", orderId);

      await tracer.startActiveSpan("validateOrder", async (childSpan) => {
        await validateOrder(orderId);
        childSpan.end();
      });

      await tracer.startActiveSpan("chargePayment", async (childSpan) => {
        await chargePayment(orderId);
        childSpan.end();
      });

      span.setStatus({ code: SpanStatusCode.OK });
    } catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
      throw error;
    } finally {
      span.end();
    }
  });
}
```

### When to use OpenTelemetry

- Multiple services communicating over HTTP/gRPC/queues
- Need to trace a request across service boundaries
- Performance debugging in distributed systems
- Not needed for single-service monoliths (Pino logs + request timing suffice)

## Metrics (optional)

For services that need quantitative monitoring beyond logs and traces.

### Key metrics to track

- **Request rate**: requests per second by endpoint and status code
- **Request duration**: p50, p95, p99 latency by endpoint
- **Error rate**: percentage of 5xx responses
- **Queue depth**: messages waiting to be processed
- **Connection pool**: active vs idle connections
- **Business metrics**: orders created, payments processed, users registered

### Implementation

Use Prometheus client or OpenTelemetry metrics exporter — framework-specific. The metrics endpoint (`/metrics`) should be on a separate port or behind auth.

## Graceful Shutdown

Ensure clean shutdown on SIGTERM/SIGINT.

```ts
/**
 * Sets up graceful shutdown handlers for the application.
 */
function setupGracefulShutdown(app: Application, db: Database, redis?: Redis) {
  let isShuttingDown = false;

  async function shutdown(signal: string) {
    if (isShuttingDown) return;
    isShuttingDown = true;

    logger.info({ signal }, "Shutdown signal received, closing gracefully");

    // Stop accepting new requests
    await app.close();
    logger.info("HTTP server closed");

    // Close database connections
    await db.close();
    logger.info("Database connections closed");

    // Close Redis
    if (redis) {
      await redis.quit();
      logger.info("Redis connection closed");
    }

    logger.info("Graceful shutdown complete");
    process.exit(0);
  }

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}
```
