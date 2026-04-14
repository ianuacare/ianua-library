# Database Patterns

Patterns for reliable, performant database access in backend TypeScript. Confirm ORM-specific syntax with the **official docs** of the ORM in use (Prisma, Drizzle, TypeORM, Knex, etc.).

## Migration Strategy

### Principles

- Migrations are **immutable** once applied — never edit a deployed migration
- Each migration does one thing (add table, add column, add index)
- Migrations must be **reversible** — always write an `up` and `down`
- Name migrations descriptively: `20260315_add_users_table.ts`, `20260316_add_email_index_to_users.ts`
- Test migrations against a copy of production data before deploying

### Safe migration patterns

- **Add column**: add as nullable first, backfill, then add NOT NULL constraint
- **Rename column**: add new column, copy data, update code, drop old column (multi-step)
- **Drop column**: remove code references first, then drop column in a later migration
- **Add index**: use `CREATE INDEX CONCURRENTLY` (PostgreSQL) to avoid table locks

### Dangerous operations

- Adding NOT NULL without default on a populated table
- Dropping columns still referenced by code
- Running data transforms in the same migration as schema changes
- Long-running migrations on large tables without `CONCURRENTLY`

## Connection Pooling

- Always use a connection pool — never open individual connections
- Configure pool size based on: `max_connections / number_of_instances`
- Typical values: min 2, max 10-20 per instance
- Set connection timeout (5s) and idle timeout (30s)
- Monitor pool usage — exhausted pools cause request queuing

```ts
// Example: generic pool config (adapt to your ORM)
const poolConfig = {
  min: 2,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
};
```

## Transaction Patterns

### Unit of Work

Group related writes in a single transaction.

```ts
/**
 * Creates an order with its line items in a single transaction.
 * @param input - The order creation input
 * @returns The created order with items
 * @throws InsufficientStockError if any item is out of stock
 */
async function createOrder(input: CreateOrderInput): Promise<Order> {
  return db.transaction(async (tx) => {
    const order = await tx.insert(orders).values({ userId: input.userId }).returning();

    for (const item of input.items) {
      await tx.insert(orderItems).values({
        orderId: order[0].id,
        productId: item.productId,
        quantity: item.quantity,
      });

      // Decrement stock within the same transaction
      await tx.update(products)
        .set({ stock: sql`stock - ${item.quantity}` })
        .where(eq(products.id, item.productId));
    }

    return order[0];
  });
}
```

### Transaction guidelines

- Keep transactions short — long transactions hold locks and block others
- Never perform I/O (HTTP calls, file reads) inside a transaction
- Use `SERIALIZABLE` isolation only when necessary (default: `READ COMMITTED`)
- Handle deadlocks with retry logic (max 3 retries with exponential backoff)

## N+1 Prevention

The N+1 problem: fetching a list (1 query), then fetching related data for each item (N queries).

### Solutions

1. **Eager loading / joins**: load related data in the same query
2. **Batch loading**: collect IDs, fetch all related data in one query
3. **DataLoader pattern**: automatic batching and caching within a request

```ts
// BAD: N+1
const users = await db.select().from(usersTable);
for (const user of users) {
  const orders = await db.select().from(ordersTable).where(eq(ordersTable.userId, user.id));
}

// GOOD: Join
const usersWithOrders = await db
  .select()
  .from(usersTable)
  .leftJoin(ordersTable, eq(usersTable.id, ordersTable.userId));

// GOOD: Batch
const users = await db.select().from(usersTable);
const userIds = users.map((u) => u.id);
const orders = await db.select().from(ordersTable).where(inArray(ordersTable.userId, userIds));
```

### Detection

- Enable query logging in development
- Use ORM-specific tools to detect N+1 (e.g. Prisma `metrics`, custom middleware)
- Review any loop that contains a database call

## Soft Delete

Use soft delete when you need audit trails or recoverability.

```ts
// Schema
const usersTable = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  deletedAt: timestamp("deleted_at"),
});

// Query: always filter out deleted records
const activeUsers = await db
  .select()
  .from(usersTable)
  .where(isNull(usersTable.deletedAt));
```

### Considerations

- Add `deletedAt` filter to all default queries (use a base repository or middleware)
- Unique constraints must account for soft-deleted records (partial unique index)
- Schedule hard deletion of old soft-deleted records (GDPR compliance)

## Audit Columns

Every table should have standard audit columns:

```ts
const baseColumns = {
  id: uuid("id").primaryKey().defaultRandom(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
};
```

- Use database triggers or ORM hooks to auto-update `updatedAt`
- For audit-sensitive tables, add `createdBy` and `updatedBy` (user ID)

## UUIDv7

Prefer UUIDv7 over UUIDv4 for primary keys:

- **Sortable by creation time** — better index performance (no random scatter)
- **Globally unique** — safe for distributed systems
- **No sequential guessing** — unlike auto-increment integers

```ts
import { uuidv7 } from "uuidv7";

const id = uuidv7(); // Monotonically increasing, time-sortable
```

## Index Strategy

### When to add indexes

- Columns used in `WHERE` clauses frequently
- Columns used in `JOIN` conditions
- Columns used in `ORDER BY`
- Foreign key columns (most databases don't auto-index these)

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

Encapsulate data access behind a typed interface.

```ts
/**
 * Repository for user data access operations.
 */
interface UserRepository {
  /** Find a user by their unique ID. */
  findById(id: UserId): Promise<User | null>;

  /** Find a user by email address. */
  findByEmail(email: string): Promise<User | null>;

  /** Find users matching the given filter with pagination. */
  findMany(filter: UserFilter, pagination: PaginationParams): Promise<PaginatedResult<User>>;

  /** Create a new user. */
  create(data: CreateUserData): Promise<User>;

  /** Update an existing user. Returns null if not found. */
  update(id: UserId, data: UpdateUserData): Promise<User | null>;

  /** Soft-delete a user. Returns true if the user existed. */
  delete(id: UserId): Promise<boolean>;
}
```

### Implementation

- Repository returns **domain objects**, not ORM entities
- Map ORM results to domain types in the repository
- Keep ORM-specific code contained — if you swap ORMs, only repositories change
- One repository per aggregate root (not per table)

## Drizzle-Specific Patterns

```ts
// Schema definition with relations
export const users = pgTable("users", {
  id: uuid("id").primaryKey().$defaultFn(() => uuidv7()),
  email: varchar("email", { length: 255 }).notNull().unique(),
  name: varchar("name", { length: 100 }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const usersRelations = relations(users, ({ many }) => ({
  orders: many(orders),
}));
```

## Prisma-Specific Patterns

```prisma
model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String
  orders    Order[]
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")

  @@map("users")
}
```

- Use `@map` and `@@map` to keep Prisma naming (camelCase) separate from DB naming (snake_case)
- Use Prisma Client extensions for soft delete, audit logging
- Use `$transaction` with interactive transactions for complex operations
