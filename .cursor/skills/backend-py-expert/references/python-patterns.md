# Python Patterns (Backend)

Framework-agnostic patterns for backend Python. Confirm syntax with the **official docs** of the framework in use.

## NewType

Use `NewType` to prevent mixing semantically different values that share the same primitive type.

```python
from typing import NewType

UserId = NewType("UserId", str)
OrderId = NewType("OrderId", str)

def get_user(user_id: UserId) -> User:
    """Fetch a user by their unique ID."""
    ...

# Type checker catches this
order_id = OrderId("abc")
get_user(order_id)  # mypy error: Argument 1 has incompatible type "OrderId"; expected "UserId"
```

### When to use

- Entity IDs that must not be confused (`UserId` vs `OrderId` vs `ProductId`)
- Units of measurement (`Milliseconds` vs `Seconds`)
- Validated strings (`Email`, `Url`, `NonEmptyString`)

## Annotated

Use `Annotated` to attach metadata to types for validation, DI, and documentation.

```python
from typing import Annotated
from pydantic import Field

PositiveInt = Annotated[int, Field(gt=0)]
Email = Annotated[str, Field(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")]

# FastAPI dependency injection
from fastapi import Depends, Header

CurrentUser = Annotated[User, Depends(get_current_user)]
ApiKey = Annotated[str, Header(alias="x-api-key")]
```

### When to use

- Pydantic field constraints without subclassing
- FastAPI dependency injection signatures
- Runtime metadata that type checkers preserve

## Protocol

Use `Protocol` for structural subtyping (duck typing with type safety).

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Repository(Protocol[T]):
    """Generic repository interface for data access."""

    async def find_by_id(self, id: str) -> T | None: ...
    async def create(self, data: dict[str, object]) -> T: ...
    async def update(self, id: str, data: dict[str, object]) -> T | None: ...
    async def delete(self, id: str) -> bool: ...


class UserRepository:
    """Concrete repository — satisfies Repository[User] without explicit inheritance."""

    async def find_by_id(self, id: str) -> User | None:
        ...

    async def create(self, data: dict[str, object]) -> User:
        ...

    async def update(self, id: str, data: dict[str, object]) -> User | None:
        ...

    async def delete(self, id: str) -> bool:
        ...
```

### When to use

- Defining interfaces for dependency injection without inheritance coupling
- Repository, service, and adapter contracts
- When you want type safety without forcing classes to inherit from an ABC

## Dataclasses vs Pydantic

### Dataclasses — internal domain objects

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True, slots=True)
class User:
    """Domain user entity."""

    id: UserId
    email: str
    name: str
    role: str = "user"
    created_at: datetime = field(default_factory=datetime.utcnow)
```

### Pydantic — boundary validation

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    """Input schema for user creation endpoint."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(default="user", pattern=r"^(admin|user|viewer)$")

class UserResponse(BaseModel):
    """Output schema for user endpoints."""

    id: str
    email: str
    name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

### When to use which

| Use dataclasses | Use Pydantic |
|---|---|
| Internal domain objects | API request/response schemas |
| Value objects, DTOs between layers | External data validation |
| When you don't need validation | When you need serialization/deserialization |
| Performance-sensitive internal code | Boundary validation (routes, consumers) |

## Generics

### TypeVar

```python
from typing import TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=Exception)

async def find_or_raise(repo: Repository[T], id: str, error: E) -> T:
    """Find an entity by ID or raise the given error."""
    result = await repo.find_by_id(id)
    if result is None:
        raise error
    return result
```

### ParamSpec

Preserve function signatures in decorators.

```python
from typing import ParamSpec, TypeVar, Callable, Awaitable
from functools import wraps

P = ParamSpec("P")
R = TypeVar("R")

def log_call(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Decorator that logs function entry and exit."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.info("calling %s", func.__name__)
        result = await func(*args, **kwargs)
        logger.info("completed %s", func.__name__)
        return result

    return wrapper
```

## Overloads

Provide precise return types based on input.

```python
from typing import overload, Literal

@overload
def get_setting(key: str, required: Literal[True]) -> str: ...
@overload
def get_setting(key: str, required: Literal[False] = ...) -> str | None: ...

def get_setting(key: str, required: bool = False) -> str | None:
    """Retrieve a configuration setting by key.

    Args:
        key: The setting name.
        required: If True, raises KeyError when the setting is missing.

    Returns:
        The setting value, or None if not required and missing.

    Raises:
        KeyError: If required is True and the setting is not found.
    """
    value = os.environ.get(key)
    if value is None and required:
        raise KeyError(f"Missing required setting: {key}")
    return value
```

## Result Pattern

Replace raise/except with explicit success/failure return types.

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

### Usage in services

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
```

### When to use

- Service methods that can fail in **domain-meaningful** ways
- When callers need to handle different error types differently
- Prefer over raising when the failure is expected (not exceptional)

## StrEnum and Literal

### StrEnum — when you need runtime enumeration

```python
from enum import StrEnum

class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class ErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    CONFLICT = "CONFLICT"
```

### Literal — when you need compile-time narrowing

```python
from typing import Literal

Status = Literal["pending", "processing", "completed", "failed"]

def transition_order(order: Order, new_status: Status) -> Order:
    ...
```

## TypeGuard

Narrow types safely at runtime.

```python
from typing import TypeGuard

def is_not_none(value: T | None) -> TypeGuard[T]:
    """Type-safe None check."""
    return value is not None

# Filter with type narrowing
valid_users: list[User] = [u for u in users if is_not_none(u)]


def is_app_error(error: Exception) -> TypeGuard[AppError]:
    """Check if an exception is a domain AppError."""
    return isinstance(error, AppError)
```

## What to Avoid

- `Any` — use `object` and narrow, or proper generics
- `type: ignore` without a tracking issue — fix the type error or document why it's unavoidable
- Bare `dict` / `list` without type parameters — always use `dict[str, object]`, `list[User]`
- `eval()` / `exec()` on any input — security risk and type-unsafe
- Mutable default arguments — use `field(default_factory=...)` or `None` sentinel
- Star imports (`from module import *`) — pollutes namespace, breaks type checking
- Bare `except:` or `except Exception:` without re-raise — silently swallows errors
