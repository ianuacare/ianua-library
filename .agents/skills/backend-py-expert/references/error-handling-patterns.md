# Error Handling Patterns

Patterns for consistent, typed error handling in backend Python. Never let errors escape unhandled. Make error paths as explicit as success paths.

## Error Hierarchy

Define a base `AppError` and extend it for domain-specific errors.

```python
from dataclasses import dataclass, field


class AppError(Exception):
    """Base application error. All custom errors extend this class.

    Provides a machine-readable code, HTTP status code, and optional context.

    Attributes:
        code: Machine-readable error code (e.g. "NOT_FOUND").
        status_code: HTTP status code to return.
        context: Additional context for debugging.
    """

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.context = context or {}
```

### Domain errors

```python
class NotFoundError(AppError):
    """Resource not found."""

    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, resource: str, id: str) -> None:
        super().__init__(f"{resource} with id {id} not found", {"resource": resource, "id": id})


class ValidationError(AppError):
    """Input validation failed."""

    code = "VALIDATION_ERROR"
    status_code = 400

    def __init__(self, message: str, details: object | None = None) -> None:
        super().__init__(message, {"details": details})


class ConflictError(AppError):
    """Resource conflict (duplicate, state conflict)."""

    code = "CONFLICT"
    status_code = 409


class UnauthorizedError(AppError):
    """Authentication required."""

    code = "UNAUTHORIZED"
    status_code = 401

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    """Insufficient permissions."""

    code = "FORBIDDEN"
    status_code = 403

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class InternalError(AppError):
    """Unexpected internal error."""

    code = "INTERNAL_ERROR"
    status_code = 500
```

## Result Pattern

An alternative to raising — make success and failure explicit in the return type.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Successful result."""
    value: T


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Failed result."""
    error: E


Result = Union[Ok[T], Err[E]]
```

### Usage

```python
async def create_user(input: CreateUserRequest) -> Result[User, UserAlreadyExistsError]:
    """Create a new user account.

    Args:
        input: Validated user creation input.

    Returns:
        Ok with the created user, or Err with a domain error.
    """
    existing = await user_repo.find_by_email(input.email)
    if existing:
        return Err(UserAlreadyExistsError(input.email))
    user = await user_repo.create(input)
    return Ok(user)


# Caller handles both cases explicitly
result = await create_user(input_data)
if isinstance(result, Err):
    logger.warning("Duplicate user creation attempt", email=input_data.email)
    raise result.error  # Let exception handler map to HTTP response
return UserResponse.model_validate(result.value)
```

### Result vs Raise — When to use which

| Use Result | Use Raise |
|---|---|
| Expected failure (duplicate email, insufficient funds) | Unexpected failure (DB connection lost, null reference) |
| Caller must handle the specific error type | Error should bubble up to a global handler |
| Multiple error types the caller distinguishes | Single "something went wrong" path |
| Functional composition of operations | Simple request handlers |

**Pick one pattern per project** and be consistent. Mixing both causes confusion.

## Exception Handlers

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map AppError instances to structured HTTP responses.

    Args:
        request: The incoming request.
        exc: The raised AppError.

    Returns:
        JSON response with error envelope.
    """
    request_id = request.headers.get("x-request-id", "unknown")
    logger.warning(
        "Application error",
        error_code=exc.code,
        status_code=exc.status_code,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": str(exc),
                "details": exc.context.get("details"),
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Log full stack, return generic message.

    Args:
        request: The incoming request.
        exc: The unhandled exception.

    Returns:
        Generic 500 JSON response.
    """
    request_id = request.headers.get("x-request-id", "unknown")
    logger.error("Unhandled error", exc_info=exc, request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        },
    )
```

### Django REST Framework

```python
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Custom DRF exception handler that wraps errors in standard envelope.

    Args:
        exc: The raised exception.
        context: DRF context dict with request, view, etc.

    Returns:
        Response with error envelope, or None to fall through to default.
    """
    if isinstance(exc, AppError):
        return Response(
            {"error": {"code": exc.code, "message": str(exc), "details": exc.context.get("details")}},
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    return None  # Let Django handle truly unhandled exceptions
```

## Error Codes Enum

Centralize error codes for consistency.

```python
from enum import StrEnum


class ErrorCode(StrEnum):
    """Machine-readable error codes."""

    # Client errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"

    # Domain errors
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    ORDER_ALREADY_SHIPPED = "ORDER_ALREADY_SHIPPED"
    USER_SUSPENDED = "USER_SUSPENDED"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
```

## Async Boundaries

Handle errors at async boundaries — don't let exceptions escape silently.

```python
import asyncio

# BAD: unhandled exception in task
async def main() -> None:
    asyncio.create_task(process_order(order))  # If this raises, it's unhandled

# GOOD: TaskGroup (Python 3.11+)
async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(process_order(order))
    # Exceptions propagate and cancel sibling tasks

# GOOD: explicit error handling for fire-and-forget
async def safe_process_order(order: Order) -> None:
    """Process order with error handling for background execution."""
    try:
        await process_order(order)
    except Exception:
        logger.error("Failed to process order", order_id=order.id, exc_info=True)
```

## Global Handlers

Set up global handlers for truly unexpected errors.

```python
import sys
import logging

def setup_global_handlers() -> None:
    """Configure global exception handlers for safety net logging."""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception
```

These are **safety nets**, not error handling strategies. If they fire, something is wrong with the code.
