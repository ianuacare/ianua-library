# Database Patterns

Patterns for reliable, performant database access in backend Python. Confirm ORM-specific syntax with the **official docs** of the ORM in use (SQLAlchemy, Django ORM, Tortoise ORM, etc.).

## Migration Strategy (Alembic)

### Principles

- Migrations are **immutable** once applied — never edit a deployed migration
- Each migration does one thing (add table, add column, add index)
- Migrations must be **reversible** — always write an `upgrade()` and `downgrade()`
- Name migrations descriptively: Alembic auto-generates a revision ID, add a message: `alembic revision -m "add_users_table"`
- Test migrations against a copy of production data before deploying

### Safe migration patterns

- **Add column**: add as nullable first, backfill, then add NOT NULL constraint
- **Rename column**: add new column, copy data, update code, drop old column (multi-step)
- **Drop column**: remove code references first, then drop column in a later migration
- **Add index**: use `CREATE INDEX CONCURRENTLY` (PostgreSQL) to avoid table locks

```python
"""Add email index to users table."""

from alembic import op

def upgrade() -> None:
    op.execute("CREATE INDEX CONCURRENTLY ix_users_email ON users (email)")

def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
```

### Dangerous operations

- Adding NOT NULL without default on a populated table
- Dropping columns still referenced by code
- Running data transforms in the same migration as schema changes
- Long-running migrations on large tables without `CONCURRENTLY`

### Django migrations

- Use `makemigrations` and `migrate` — same principles apply
- Use `RunSQL` for raw SQL operations in Django migrations
- Use `SeparateDatabaseAndState` for complex column renames

## Connection Pooling

### SQLAlchemy (sync)

```python
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,      # Recycle connections after 30 min
    pool_pre_ping=True,     # Verify connections before use
)
```

### SQLAlchemy (async)

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)
```

### Guidelines

- Always use a connection pool — never open individual connections
- Configure pool size based on: `max_connections / number_of_instances`
- Typical values: `pool_size=10`, `max_overflow=5` per instance
- Set `pool_pre_ping=True` to handle stale connections
- Monitor pool usage — exhausted pools cause request queuing

## Transaction Patterns

### Context manager (SQLAlchemy)

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def create_order(session: AsyncSession, input: CreateOrderInput) -> Order:
    """Create an order with line items in a single transaction.

    Args:
        session: Database session (transaction boundary).
        input: Order creation input.

    Returns:
        The created order with items.

    Raises:
        InsufficientStockError: If any item is out of stock.
    """
    async with session.begin():
        order = Order(user_id=input.user_id)
        session.add(order)
        await session.flush()  # Get order.id

        for item in input.items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
            )
            session.add(order_item)

        return order
```

### Transaction guidelines

- Keep transactions short — long transactions hold locks and block others
- Never perform I/O (HTTP calls, file reads) inside a transaction
- Use `SERIALIZABLE` isolation only when necessary (default: `READ COMMITTED`)
- Handle deadlocks with retry logic (max 3 retries with exponential backoff)

### Django transactions

```python
from django.db import transaction

@transaction.atomic
def create_order(input: CreateOrderInput) -> Order:
    """Create an order atomically."""
    order = Order.objects.create(user_id=input.user_id)
    for item in input.items:
        OrderItem.objects.create(order=order, **item)
    return order
```

## N+1 Prevention

The N+1 problem: fetching a list (1 query), then fetching related data for each item (N queries).

### SQLAlchemy solutions

```python
from sqlalchemy.orm import selectinload, joinedload

# BAD: N+1
users = await session.execute(select(User))
for user in users.scalars():
    orders = await session.execute(
        select(Order).where(Order.user_id == user.id)
    )

# GOOD: selectinload (separate IN query)
stmt = select(User).options(selectinload(User.orders))
users = await session.execute(stmt)

# GOOD: joinedload (single JOIN query)
stmt = select(User).options(joinedload(User.orders))
users = await session.execute(stmt)
```

### Django solutions

```python
# BAD: N+1
users = User.objects.all()
for user in users:
    orders = user.orders.all()  # Separate query per user

# GOOD: select_related (JOIN, for ForeignKey/OneToOne)
orders = Order.objects.select_related("user").all()

# GOOD: prefetch_related (separate query, for ManyToMany/reverse FK)
users = User.objects.prefetch_related("orders").all()
```

### Detection

- Enable query logging in development (`SQLALCHEMY_ECHO=True`, Django `django-debug-toolbar`)
- Review any loop that contains a database call
- Use `nplusone` library for automatic N+1 detection in Django

## Soft Delete

Use soft delete when you need audit trails or recoverability.

```python
from sqlalchemy import Column, DateTime
from sqlalchemy.orm import DeclarativeBase

class SoftDeleteMixin:
    """Mixin for soft-deletable models."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

### Considerations

- Add `deleted_at IS NULL` filter to all default queries (use a custom query class or manager)
- Unique constraints must account for soft-deleted records (partial unique index)
- Schedule hard deletion of old soft-deleted records (GDPR compliance)

## Audit Columns

Every table should have standard audit columns:

```python
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

class AuditMixin:
    """Mixin providing standard audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
```

- Use database triggers or ORM events to auto-update `updated_at`
- For audit-sensitive tables, add `created_by` and `updated_by` (user ID)

## UUIDv7

Prefer UUIDv7 over UUIDv4 for primary keys:

- **Sortable by creation time** — better index performance (no random scatter)
- **Globally unique** — safe for distributed systems
- **No sequential guessing** — unlike auto-increment integers

```python
from uuid_utils import uuid7  # or uuid6 library

class Base(DeclarativeBase):
    """Base model with UUIDv7 primary key."""

    id: Mapped[str] = mapped_column(
        Uuid, primary_key=True, default=uuid7
    )
```

## Index Strategy

### When to add indexes

- Columns used in `WHERE` clauses frequently
- Columns used in `JOIN` conditions
- Columns used in `ORDER BY`
- Foreign key columns (PostgreSQL doesn't auto-index these)

### Types

- **B-tree** (default): equality and range queries
- **Hash**: equality-only (rarely needed, B-tree covers this)
- **GIN**: full-text search, JSONB containment, array elements
- **Partial index**: index only rows matching a condition (e.g. `WHERE deleted_at IS NULL`)
- **Composite index**: multi-column, column order matters (left-to-right)

### Guidelines

- Don't index everything — each index slows writes
- Monitor query plans (`EXPLAIN ANALYZE`) to verify indexes are used
- Remove unused indexes (track via `pg_stat_user_indexes`)

## Repository Pattern

Encapsulate data access behind a typed Protocol.

```python
from typing import Protocol

class UserRepository(Protocol):
    """Repository interface for user data access."""

    async def find_by_id(self, id: UserId) -> User | None:
        """Find a user by their unique ID."""
        ...

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email address."""
        ...

    async def find_many(
        self, filter: UserFilter, pagination: PaginationParams
    ) -> PaginatedResult[User]:
        """Find users matching the given filter with pagination."""
        ...

    async def create(self, data: CreateUserData) -> User:
        """Create a new user."""
        ...

    async def update(self, id: UserId, data: UpdateUserData) -> User | None:
        """Update an existing user. Returns None if not found."""
        ...

    async def delete(self, id: UserId) -> bool:
        """Soft-delete a user. Returns True if the user existed."""
        ...
```

### Implementation

- Repository returns **domain objects** (dataclasses), not ORM models
- Map ORM results to domain types in the repository
- Keep ORM-specific code contained — if you swap ORMs, only repositories change
- One repository per aggregate root (not per table)

## SQLAlchemy 2.x Patterns

### Declarative models with mapped_column

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
```

### Async session factory

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        yield session
```

## Django ORM Patterns

### Model with mixins

```python
from django.db import models
import uuid

class AuditModel(models.Model):
    """Abstract base model with audit fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, default="user")
```

- Use `select_related` and `prefetch_related` to avoid N+1
- Use `F()` expressions for atomic updates
- Use `Q()` objects for complex filters
