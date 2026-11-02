# Testing Patterns

Patterns for thorough, maintainable backend tests in Python. Unit tests are the **foundation** — every service and handler must be tested. Minimum coverage target: **>80%**. Confirm test runner syntax with the **official docs** of pytest.

## Unit Tests — The Foundation

Unit tests verify individual functions and methods in isolation. They are fast, deterministic, and form the bulk of your test suite.

### Structure

```python
import pytest
from unittest.mock import AsyncMock

class TestUserService:
    """Tests for UserService."""

    async def test_create_user_with_valid_input(self) -> None:
        """Should create a user with valid input."""
        # Arrange
        input_data = UserFactory.create_input()
        mock_repo = create_mock_user_repository()
        mock_repo.find_by_email.return_value = None
        mock_repo.create.return_value = UserFactory.create(**input_data.model_dump())
        service = UserService(repo=mock_repo)

        # Act
        result = await service.create_user(input_data)

        # Assert
        assert isinstance(result, Ok)
        assert result.value.email == input_data.email

    async def test_create_user_returns_error_if_email_exists(self) -> None:
        """Should return error if email already exists."""
        # Arrange
        input_data = UserFactory.create_input()
        mock_repo = create_mock_user_repository()
        mock_repo.find_by_email.return_value = UserFactory.create()
        service = UserService(repo=mock_repo)

        # Act
        result = await service.create_user(input_data)

        # Assert
        assert isinstance(result, Err)
        assert isinstance(result.error, UserAlreadyExistsError)

    async def test_create_user_hashes_password(self) -> None:
        """Should hash the password before storing."""
        ...

    async def test_create_user_trims_email_whitespace(self) -> None:
        """Should trim whitespace from email."""
        ...
```

### What to test

For every service method and handler, test:

1. **Happy path** — correct input produces correct output
2. **Edge cases** — empty strings, boundary values, None where possible
3. **Error scenarios** — invalid input, missing dependencies, domain rule violations
4. **Side effects** — verify the right repository methods were called with the right arguments

### Coverage target

- **>80%** overall on new code
- **100%** on business logic (services, domain functions)
- Acceptable to have lower coverage on glue code (DI wiring, config parsing)
- Coverage is a floor, not a ceiling — aim for meaningful tests, not line-count gaming

## Factory Pattern with factory_boy

Use `factory_boy` to create test data. Never scatter raw dict literals across test files.

```python
# tests/factories/user_factory.py

import factory
from faker import Faker

fake = Faker()


class UserFactory(factory.Factory):
    """Factory for creating test User objects."""

    class Meta:
        model = User

    id = factory.LazyFunction(lambda: str(uuid7()))
    email = factory.LazyFunction(fake.email)
    name = factory.LazyFunction(fake.name)
    role = "user"
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class CreateUserRequestFactory(factory.Factory):
    """Factory for creating test CreateUserRequest objects."""

    class Meta:
        model = CreateUserRequest

    email = factory.LazyFunction(fake.email)
    name = factory.LazyFunction(fake.name)
    role = "user"
```

### Benefits

- Single source of truth for test data shape
- Easy to override specific fields per test: `UserFactory.create(role="admin")`
- Keeps tests focused on what varies, not setup boilerplate

## Fixtures

Use pytest fixtures for setup/teardown and shared test dependencies.

```python
# conftest.py

import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Mock UserRepository with all methods as AsyncMock."""
    repo = AsyncMock(spec=UserRepository)
    repo.find_by_id.return_value = None
    repo.find_by_email.return_value = None
    return repo

@pytest.fixture
def user_service(mock_user_repo: AsyncMock) -> UserService:
    """UserService with mocked dependencies."""
    return UserService(repo=mock_user_repo)
```

### Fixture scoping

| Scope | Lifetime | Use for |
|---|---|---|
| `function` (default) | Each test | Most unit test fixtures |
| `class` | Each test class | Shared setup within a test class |
| `module` | Each test module | Expensive setup shared across tests in a file |
| `session` | Entire test session | Database containers, app instances |

## Parametrize

Test multiple scenarios without duplicating test code.

```python
@pytest.mark.parametrize(
    "role,expected_permissions",
    [
        ("admin", {"read", "write", "delete", "manage_users"}),
        ("user", {"read", "write"}),
        ("viewer", {"read"}),
    ],
)
def test_get_permissions_for_role(role: str, expected_permissions: set[str]) -> None:
    """Should return correct permissions for each role."""
    assert get_permissions(role) == expected_permissions


@pytest.mark.parametrize(
    "email,is_valid",
    [
        ("user@example.com", True),
        ("user@sub.domain.com", True),
        ("invalid", False),
        ("", False),
        ("@domain.com", False),
    ],
)
def test_email_validation(email: str, is_valid: bool) -> None:
    """Should validate email addresses correctly."""
    if is_valid:
        result = CreateUserRequest(email=email, name="Test")
        assert result.email == email
    else:
        with pytest.raises(ValidationError):
            CreateUserRequest(email=email, name="Test")
```

## Mocking Strategy

### What to mock

- **External HTTP clients** — never make real HTTP calls in unit tests (`httpx`, `aiohttp`)
- **Third-party SDKs** — payment providers, email services, cloud APIs
- **Time** — use `freezegun` or `time-machine` when testing time-dependent logic
- **Random values** — seed or mock UUID generation when determinism matters

### What NOT to mock

- **Internal business logic** — if you're mocking the function you're testing, the test is meaningless
- **Data transformations** — test the actual mapping, don't mock it away
- **Pydantic schemas** — validate with real schemas to catch schema drift

### Mock creation

```python
from unittest.mock import AsyncMock, MagicMock, patch

def create_mock_user_repository() -> AsyncMock:
    """Create a mock UserRepository with AsyncMock methods."""
    return AsyncMock(spec=UserRepository)


# Patching external calls
@patch("app.services.user_service.send_welcome_email")
async def test_create_user_sends_welcome_email(
    mock_send_email: AsyncMock,
    user_service: UserService,
) -> None:
    """Should send welcome email after user creation."""
    input_data = CreateUserRequestFactory.create()
    await user_service.create_user(input_data)
    mock_send_email.assert_called_once()
```

## Integration Tests

Test the repository layer against a **real database**. Use Docker or testcontainers.

### Testcontainers setup

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for integration tests."""
    with PostgresContainer("postgres:16") as container:
        yield container

@pytest.fixture(scope="session")
async def db_engine(postgres_container):
    """Create database engine connected to test container."""
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with async_session(bind=db_engine) as session:
        yield session
        await session.rollback()
```

### What to test in integration tests

- CRUD operations work correctly with real SQL
- Constraints and unique indexes are enforced
- Complex queries return correct results
- Transactions commit and rollback as expected
- Migrations apply cleanly

## API / E2E Tests

Test the full request/response cycle with TestClient or httpx.

### FastAPI TestClient

```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestCreateUser:
    """E2E tests for POST /users."""

    async def test_creates_user_and_returns_201(self, client: AsyncClient) -> None:
        """Should create a user and return 201."""
        response = await client.post(
            "/users",
            json={"email": "test@example.com", "name": "Test User"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["data"]["email"] == "test@example.com"

    async def test_returns_400_for_invalid_email(self, client: AsyncClient) -> None:
        """Should return 400 for invalid email."""
        response = await client.post(
            "/users",
            json={"email": "not-an-email", "name": "Test User"},
        )

        assert response.status_code == 422  # FastAPI validation

    async def test_returns_409_if_email_exists(self, client: AsyncClient) -> None:
        """Should return 409 if email already exists."""
        payload = {"email": "dup@example.com", "name": "First"}
        await client.post("/users", json=payload)

        response = await client.post("/users", json=payload)

        assert response.status_code == 409
```

## Property-Based Testing with Hypothesis

Use Hypothesis for testing invariants with random input.

```python
from hypothesis import given, strategies as st

@given(
    total=st.integers(min_value=0, max_value=10000),
    page_size=st.integers(min_value=1, max_value=100),
    page=st.integers(min_value=1, max_value=100),
)
def test_pagination_always_returns_valid_metadata(
    total: int, page_size: int, page: int
) -> None:
    """Should always return valid pagination metadata."""
    result = calculate_pagination(total, page_size, page)
    assert result.total_pages >= 0
    assert result.total_pages == -(-total // page_size)  # ceil division
    assert result.has_more == (page < result.total_pages)
```

### When to use

- Pure functions with wide input ranges (parsing, validation, math)
- Serialization/deserialization roundtrips
- Invariants that must hold for any input

## Test Organization

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_user_service.py
│   │   └── test_order_service.py
│   └── handlers/
│       ├── test_create_user_handler.py
│       └── test_list_orders_handler.py
├── integration/
│   ├── repositories/
│   │   ├── test_user_repository.py
│   │   └── test_order_repository.py
│   └── conftest.py
├── e2e/
│   ├── test_users.py
│   └── test_orders.py
├── factories/
│   ├── user_factory.py
│   └── order_factory.py
└── conftest.py
```

## Test Naming

- Class names: `TestServiceMethod` or `TestEndpoint` (e.g. `TestCreateUser`)
- Method names: `test_` prefix + descriptive behavior (e.g. `test_returns_404_when_user_not_found`)
- Be specific: `test_returns_404_when_user_not_found` not `test_handles_errors`
- Use docstrings for human-readable descriptions shown in test output

## pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]
markers = [
    "integration: marks tests that require external services",
    "e2e: marks end-to-end tests",
]
```
