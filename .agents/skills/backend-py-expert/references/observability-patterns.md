# Observability Patterns

Patterns for structured logging, health checks, tracing, and monitoring in backend Python services. Confirm framework-specific integrations with the **official docs**.

## Structured Logging with structlog

### Setup

```python
import structlog
import logging

def configure_logging(environment: str = "production") -> None:
    """Configure structlog with environment-appropriate settings.

    Args:
        environment: One of "production", "development", "test".
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment == "development":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(
        logging.WARNING if environment == "test"
        else logging.INFO if environment == "production"
        else logging.DEBUG
    )
```

### Bound loggers with contextvars

Use `contextvars` for automatic context propagation across async calls.

```python
import structlog
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = structlog.get_logger()

# In middleware: bind context for the entire request
async def logging_middleware(request: Request, call_next):
    """Middleware that binds request context to structlog.

    Args:
        request: The incoming request.
        call_next: Next middleware in the chain.

    Returns:
        The response with x-request-id header.
    """
    request_id = request.headers.get("x-request-id", str(uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Request completed",
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )

    response.headers["x-request-id"] = request_id
    return response
```

### Log levels

Use appropriate levels consistently:

| Level | Use for |
|-------|---------|
| `critical` | Application is about to crash — unrecoverable |
| `error` | Operation failed — requires attention, but app continues |
| `warning` | Something unexpected but handled — degraded behavior |
| `info` | Significant business events — request completed, user created, payment processed |
| `debug` | Detailed diagnostic info — query results, intermediate state |

### Logging guidelines

- **Do** log: request start/end, business events, errors with context, external service calls
- **Don't** log: sensitive data (passwords, tokens, PII), large payloads, every function call
- **Always** include: `request_id`, relevant entity IDs, operation name
- **Never** use `print()` — always use the structured logger

```python
# GOOD
logger.info("Order created", user_id=user.id, order_id=order.id)
logger.warning("Multiple failed login attempts", user_id=user.id, attempts=failed_attempts)
logger.error("Failed to process payment", order_id=order_id, exc_info=True)

# BAD
print("User created")  # No structure, no context
logger.info(f"Order created for user {user_id}")  # f-string, no structured fields
logger.error(error)  # Missing context
```

## Correlation IDs

Propagate a unique ID through the entire request lifecycle for distributed tracing.

### Implementation

1. Extract or generate `request_id` at the entry point (middleware)
2. Bind to structlog context via `contextvars` (automatic in child log calls)
3. Pass through to external service calls via headers (`x-request-id`)
4. Include in error responses for client-side debugging
5. Include in queue messages for async operation tracing

```python
import httpx

async def call_payment_service(order_id: str, request_id: str) -> httpx.Response:
    """Call payment service with correlation ID propagation.

    Args:
        order_id: The order to charge.
        request_id: Correlation ID to propagate.

    Returns:
        Response from payment service.
    """
    async with httpx.AsyncClient() as client:
        return await client.post(
            "https://payments.internal/charge",
            json={"order_id": order_id},
            headers={"x-request-id": request_id},
        )
```

## Health Check Endpoints

### Liveness — `/health`

"Is the process running?" Used by orchestrators (Kubernetes, Docker) to restart crashed instances.

```python
@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Returns 200 if the process is running.

    Does NOT check external dependencies.

    Returns:
        Status dict.
    """
    return {"status": "ok"}
```

### Readiness — `/ready`

"Can this instance serve traffic?" Used by load balancers to route traffic.

```python
from fastapi import Response

@router.get("/ready")
async def ready(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> Response:
    """Readiness probe. Returns 200 if the service can accept requests.

    Checks database connectivity and other critical dependencies.

    Args:
        session: Database session for connectivity check.
        redis: Redis client for cache check.

    Returns:
        JSON with check results and appropriate status code.
    """
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failing"

    try:
        await redis.ping()
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "failing"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
```

### Guidelines

- Health endpoints should **not** require authentication
- Keep checks fast — timeout after 2-3 seconds
- Don't expose internal details (versions, hostnames) in production
- Separate liveness from readiness — they serve different purposes

## OpenTelemetry

For distributed tracing across multiple services.

### Setup

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

def init_telemetry(service_name: str, app: FastAPI) -> None:
    """Initialize OpenTelemetry SDK with auto-instrumentation.

    Must be called during application startup.

    Args:
        service_name: Name of this service for trace identification.
        app: FastAPI application to instrument.
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_ENDPOINT or "localhost:4317",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
```

### Custom spans

```python
from opentelemetry import trace

tracer = trace.get_tracer("order-service")

async def process_order(order_id: str) -> None:
    """Process an order with tracing for performance visibility.

    Args:
        order_id: The order to process.
    """
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)

        with tracer.start_as_current_span("validate_order"):
            await validate_order(order_id)

        with tracer.start_as_current_span("charge_payment"):
            await charge_payment(order_id)
```

### When to use OpenTelemetry

- Multiple services communicating over HTTP/gRPC/queues
- Need to trace a request across service boundaries
- Performance debugging in distributed systems
- Not needed for single-service monoliths (structlog + request timing suffice)

## Metrics (optional)

For services that need quantitative monitoring beyond logs and traces.

### Key metrics to track

- **Request rate**: requests per second by endpoint and status code
- **Request duration**: p50, p95, p99 latency by endpoint
- **Error rate**: percentage of 5xx responses
- **Queue depth**: messages waiting to be processed
- **Connection pool**: active vs idle connections
- **Business metrics**: orders created, payments processed, users registered

### Implementation with prometheus-client

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus-formatted metrics.
    """
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4",
    )
```

The metrics endpoint (`/metrics`) should be on a separate port or behind auth.

## Graceful Shutdown

Ensure clean shutdown on SIGTERM/SIGINT.

```python
import signal
import asyncio

def setup_graceful_shutdown(
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis | None = None,
) -> None:
    """Set up graceful shutdown handlers for the application.

    Args:
        app: FastAPI application.
        engine: SQLAlchemy async engine.
        redis: Optional Redis client.
    """
    is_shutting_down = False

    async def shutdown(sig: signal.Signals) -> None:
        nonlocal is_shutting_down
        if is_shutting_down:
            return
        is_shutting_down = True

        logger.info("Shutdown signal received", signal=sig.name)

        # Close database connections
        await engine.dispose()
        logger.info("Database connections closed")

        # Close Redis
        if redis is not None:
            await redis.close()
            logger.info("Redis connection closed")

        logger.info("Graceful shutdown complete")

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s)),
        )
```
