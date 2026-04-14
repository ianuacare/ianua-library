# Error Handling Patterns

Patterns for consistent, typed error handling in backend TypeScript. Never let errors escape unhandled. Make error paths as explicit as success paths.

## Error Hierarchy

Define a base `AppError` and extend it for domain-specific errors.

```ts
/**
 * Base application error. All custom errors extend this class.
 * Provides a machine-readable code, HTTP status, and optional context.
 */
export abstract class AppError extends Error {
  abstract readonly code: string;
  abstract readonly statusCode: number;
  readonly context?: Record<string, unknown>;

  constructor(message: string, context?: Record<string, unknown>) {
    super(message);
    this.name = this.constructor.name;
    this.context = context;
    Error.captureStackTrace(this, this.constructor);
  }
}
```

### Domain errors

```ts
export class NotFoundError extends AppError {
  readonly code = "NOT_FOUND";
  readonly statusCode = 404;

  constructor(resource: string, id: string) {
    super(`${resource} with id ${id} not found`, { resource, id });
  }
}

export class ValidationError extends AppError {
  readonly code = "VALIDATION_ERROR";
  readonly statusCode = 400;

  constructor(message: string, details?: unknown) {
    super(message, { details });
  }
}

export class ConflictError extends AppError {
  readonly code = "CONFLICT";
  readonly statusCode = 409;

  constructor(message: string, context?: Record<string, unknown>) {
    super(message, context);
  }
}

export class UnauthorizedError extends AppError {
  readonly code = "UNAUTHORIZED";
  readonly statusCode = 401;

  constructor(message = "Authentication required") {
    super(message);
  }
}

export class ForbiddenError extends AppError {
  readonly code = "FORBIDDEN";
  readonly statusCode = 403;

  constructor(message = "Insufficient permissions") {
    super(message);
  }
}

export class InternalError extends AppError {
  readonly code = "INTERNAL_ERROR";
  readonly statusCode = 500;

  constructor(message = "An unexpected error occurred", context?: Record<string, unknown>) {
    super(message, context);
  }
}
```

## Result Pattern

An alternative to throwing — make success and failure explicit in the return type.

```ts
type Result<T, E = AppError> =
  | { success: true; data: T }
  | { success: false; error: E };

function ok<T>(data: T): Result<T, never> {
  return { success: true, data };
}

function err<E>(error: E): Result<never, E> {
  return { success: false, error };
}
```

### Usage

```ts
/**
 * Creates a new user account.
 * @param input - Validated user creation input
 * @returns Result with the created user, or a domain error
 */
async function createUser(input: CreateUserInput): Promise<Result<User, UserAlreadyExistsError>> {
  const existing = await userRepo.findByEmail(input.email);
  if (existing) {
    return err(new UserAlreadyExistsError(input.email));
  }
  const user = await userRepo.create(input);
  return ok(user);
}

// Caller handles both cases explicitly
const result = await createUser(input);
if (!result.success) {
  // TypeScript narrows to UserAlreadyExistsError
  logger.warn({ email: input.email }, "Duplicate user creation attempt");
  return reply.status(409).send(formatError(result.error));
}
return reply.status(201).send({ data: result.data });
```

### Result vs Throw — When to use which

| Use Result | Use Throw |
|---|---|
| Expected failure (duplicate email, insufficient funds) | Unexpected failure (DB connection lost, null pointer) |
| Caller must handle the specific error type | Error should bubble up to a global handler |
| Multiple error types the caller distinguishes | Single "something went wrong" path |
| Functional composition of operations | Simple request handlers |

**Pick one pattern per project** and be consistent. Mixing both causes confusion.

## Error Middleware

Centralized error handling for frameworks that support middleware (Express, Fastify, etc.).

```ts
/**
 * Global error handler middleware.
 * Maps AppError instances to structured HTTP responses.
 * Unknown errors are logged and returned as 500.
 */
function errorHandler(error: Error, request: Request, reply: Reply) {
  const requestId = request.id ?? "unknown";

  if (error instanceof AppError) {
    request.log.warn({ err: error, requestId }, error.message);
    return reply.status(error.statusCode).send({
      error: {
        code: error.code,
        message: error.message,
        details: error.context?.details,
        requestId,
      },
    });
  }

  // Zod validation errors
  if (error.name === "ZodError") {
    request.log.warn({ err: error, requestId }, "Validation error");
    return reply.status(400).send({
      error: {
        code: "VALIDATION_ERROR",
        message: "Request validation failed",
        details: (error as ZodError).issues,
        requestId,
      },
    });
  }

  // Unknown errors — log full stack, return generic message
  request.log.error({ err: error, requestId }, "Unhandled error");
  return reply.status(500).send({
    error: {
      code: "INTERNAL_ERROR",
      message: "An unexpected error occurred",
      requestId,
    },
  });
}
```

## Error Codes Enum

Centralize error codes for consistency.

```ts
export const ErrorCode = {
  // Client errors
  VALIDATION_ERROR: "VALIDATION_ERROR",
  NOT_FOUND: "NOT_FOUND",
  CONFLICT: "CONFLICT",
  UNAUTHORIZED: "UNAUTHORIZED",
  FORBIDDEN: "FORBIDDEN",
  RATE_LIMITED: "RATE_LIMITED",

  // Domain errors
  INSUFFICIENT_FUNDS: "INSUFFICIENT_FUNDS",
  ORDER_ALREADY_SHIPPED: "ORDER_ALREADY_SHIPPED",
  USER_SUSPENDED: "USER_SUSPENDED",

  // System errors
  INTERNAL_ERROR: "INTERNAL_ERROR",
  SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
  EXTERNAL_SERVICE_ERROR: "EXTERNAL_SERVICE_ERROR",
} as const;

type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];
```

## Async Boundaries

Handle errors at async boundaries — don't let promises float.

```ts
// BAD: floating promise
app.listen(3000);

// GOOD: handle the error
app.listen(3000).catch((err) => {
  logger.fatal({ err }, "Failed to start server");
  process.exit(1);
});

// BAD: unhandled rejection in event handler
emitter.on("order.created", async (order) => {
  await processOrder(order); // If this throws, it's unhandled
});

// GOOD: wrap with error handling
emitter.on("order.created", async (order) => {
  try {
    await processOrder(order);
  } catch (error) {
    logger.error({ err: error, orderId: order.id }, "Failed to process order");
  }
});
```

## Error Context with Request ID

Every error should carry enough context for debugging.

```ts
// Middleware: assign request ID early in the pipeline
function requestIdMiddleware(request: Request, reply: Reply, next: NextFunction) {
  request.id = request.headers["x-request-id"]?.toString() ?? crypto.randomUUID();
  reply.header("x-request-id", request.id);
  next();
}

// Errors include request ID
throw new NotFoundError("User", userId);
// Error middleware adds requestId from request context
```

## Global Handlers

Set up global handlers for truly unexpected errors.

```ts
process.on("unhandledRejection", (reason) => {
  logger.fatal({ err: reason }, "Unhandled rejection — shutting down");
  process.exit(1);
});

process.on("uncaughtException", (error) => {
  logger.fatal({ err: error }, "Uncaught exception — shutting down");
  process.exit(1);
});
```

These are **safety nets**, not error handling strategies. If they fire, something is wrong with the code.
