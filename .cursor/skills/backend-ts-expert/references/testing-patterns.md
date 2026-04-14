# Testing Patterns

Patterns for thorough, maintainable backend tests. Unit tests are the **foundation** — every service and handler must be tested. Minimum coverage target: **>80%**. Confirm test runner syntax with the **official docs** of the runner in use (Vitest, Jest, etc.).

## Unit Tests — The Foundation

Unit tests verify individual functions and methods in isolation. They are fast, deterministic, and form the bulk of your test suite.

### Structure

```ts
describe("UserService", () => {
  describe("createUser", () => {
    it("should create a user with valid input", async () => {
      // Arrange
      const input = UserFactory.createInput();
      const mockRepo = createMockUserRepository();
      mockRepo.findByEmail.mockResolvedValue(null);
      mockRepo.create.mockResolvedValue(UserFactory.create(input));
      const service = new UserService(mockRepo);

      // Act
      const result = await service.createUser(input);

      // Assert
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.email).toBe(input.email);
      }
    });

    it("should return error if email already exists", async () => {
      // Arrange
      const input = UserFactory.createInput();
      const mockRepo = createMockUserRepository();
      mockRepo.findByEmail.mockResolvedValue(UserFactory.create(input));
      const service = new UserService(mockRepo);

      // Act
      const result = await service.createUser(input);

      // Assert
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error).toBeInstanceOf(UserAlreadyExistsError);
      }
    });

    it("should hash the password before storing", async () => {
      // ...
    });

    it("should trim whitespace from email", async () => {
      // ...
    });
  });
});
```

### What to test

For every service method and handler, test:

1. **Happy path** — correct input produces correct output
2. **Edge cases** — empty strings, boundary values, null/undefined where possible
3. **Error scenarios** — invalid input, missing dependencies, domain rule violations
4. **Side effects** — verify the right repository methods were called with the right arguments

### Coverage target

- **>80%** overall on new code
- **100%** on business logic (services, domain functions)
- Acceptable to have lower coverage on glue code (DI wiring, config parsing)
- Coverage is a floor, not a ceiling — aim for meaningful tests, not line-count gaming

## Factory Pattern

Use factory functions to create test data. Never scatter raw object literals across test files.

```ts
// test/factories/user.factory.ts

import { faker } from "@faker-js/faker";

/**
 * Factory for creating test User objects and related inputs.
 */
export const UserFactory = {
  /**
   * Create a full User object with optional overrides.
   */
  create(overrides: Partial<User> = {}): User {
    return {
      id: overrides.id ?? faker.string.uuid(),
      email: overrides.email ?? faker.internet.email(),
      name: overrides.name ?? faker.person.fullName(),
      role: overrides.role ?? "user",
      createdAt: overrides.createdAt ?? new Date(),
      updatedAt: overrides.updatedAt ?? new Date(),
    };
  },

  /**
   * Create a CreateUserInput with optional overrides.
   */
  createInput(overrides: Partial<CreateUserInput> = {}): CreateUserInput {
    return {
      email: overrides.email ?? faker.internet.email(),
      name: overrides.name ?? faker.person.fullName(),
      role: overrides.role ?? "user",
    };
  },

  /**
   * Create a batch of users.
   */
  createMany(count: number, overrides: Partial<User> = {}): User[] {
    return Array.from({ length: count }, () => this.create(overrides));
  },
};
```

### Benefits

- Single source of truth for test data shape
- Easy to override specific fields per test
- Keeps tests focused on what varies, not setup boilerplate

## Mocking Strategy

### What to mock

- **External HTTP clients** — never make real HTTP calls in unit tests
- **Third-party SDKs** — payment providers, email services, cloud APIs
- **Time** — use `vi.useFakeTimers()` / `jest.useFakeTimers()` when testing time-dependent logic
- **Random values** — seed or mock `Math.random`, UUID generation when determinism matters

### What NOT to mock

- **Internal business logic** — if you're mocking the function you're testing, the test is meaningless
- **Data transformations** — test the actual mapping, don't mock it away
- **Zod schemas** — validate with real schemas to catch schema drift

### Mock creation

```ts
function createMockUserRepository(): jest.Mocked<UserRepository> {
  return {
    findById: vi.fn(),
    findByEmail: vi.fn(),
    findMany: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  };
}
```

## Integration Tests

Test the repository layer against a **real database**. Use Docker or testcontainers.

### Testcontainers setup

```ts
import { PostgreSqlContainer } from "@testcontainers/postgresql";

let container: StartedPostgreSqlContainer;
let db: Database;

beforeAll(async () => {
  container = await new PostgreSqlContainer().start();
  db = createDatabase(container.getConnectionUri());
  await runMigrations(db);
}, 30_000);

afterAll(async () => {
  await db.close();
  await container.stop();
});

beforeEach(async () => {
  // Clean tables between tests
  await db.execute(sql`TRUNCATE users, orders CASCADE`);
});
```

### What to test in integration tests

- CRUD operations work correctly with real SQL
- Constraints and unique indexes are enforced
- Complex queries return correct results
- Transactions commit and rollback as expected
- Migrations apply cleanly

## API / E2E Tests

Test the full request/response cycle with supertest or equivalent.

```ts
import { buildApp } from "../src/app";

describe("POST /users", () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await buildApp({ testing: true });
  });

  afterAll(async () => {
    await app.close();
  });

  it("should create a user and return 201", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/users",
      payload: {
        email: "test@example.com",
        name: "Test User",
      },
    });

    expect(response.statusCode).toBe(201);
    const body = JSON.parse(response.body);
    expect(body.data.email).toBe("test@example.com");
  });

  it("should return 400 for invalid email", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/users",
      payload: {
        email: "not-an-email",
        name: "Test User",
      },
    });

    expect(response.statusCode).toBe(400);
    const body = JSON.parse(response.body);
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("should return 409 if email already exists", async () => {
    // Create first user
    await app.inject({
      method: "POST",
      url: "/users",
      payload: { email: "dup@example.com", name: "First" },
    });

    // Try duplicate
    const response = await app.inject({
      method: "POST",
      url: "/users",
      payload: { email: "dup@example.com", name: "Second" },
    });

    expect(response.statusCode).toBe(409);
  });
});
```

## Property-Based Testing

Use fast-check for testing invariants with random input.

```ts
import fc from "fast-check";

describe("pagination", () => {
  it("should always return valid pagination metadata", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 10000 }),  // total
        fc.integer({ min: 1, max: 100 }),     // pageSize
        fc.integer({ min: 1, max: 100 }),     // page
        (total, pageSize, page) => {
          const result = calculatePagination(total, pageSize, page);
          expect(result.totalPages).toBeGreaterThanOrEqual(0);
          expect(result.totalPages).toBe(Math.ceil(total / pageSize));
          expect(result.hasMore).toBe(page < result.totalPages);
        }
      )
    );
  });
});
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
│   │   ├── user-service.test.ts
│   │   └── order-service.test.ts
│   └── handlers/
│       ├── create-user.handler.test.ts
│       └── list-orders.handler.test.ts
├── integration/
│   ├── repositories/
│   │   ├── user-repository.test.ts
│   │   └── order-repository.test.ts
│   └── setup.ts
├── e2e/
│   ├── users.e2e.test.ts
│   └── orders.e2e.test.ts
└── factories/
    ├── user.factory.ts
    └── order.factory.ts
```

## Test Naming

- `describe` blocks: class or module name
- Nested `describe`: method name
- `it` blocks: start with "should" + expected behavior
- Be specific: "should return 404 when user does not exist" not "should handle errors"
