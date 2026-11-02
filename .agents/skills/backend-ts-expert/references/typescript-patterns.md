# TypeScript Patterns (Backend)

Framework-agnostic patterns for backend TypeScript. Confirm syntax with the **official docs** of the framework in use.

## Branded Types

Use branded types to prevent mixing semantically different values that share the same primitive type.

```ts
type UserId = string & { readonly __brand: "UserId" };
type OrderId = string & { readonly __brand: "OrderId" };

function createUserId(id: string): UserId {
  return id as UserId;
}

function getUser(id: UserId): Promise<User> { /* ... */ }

// Compile error: Argument of type 'OrderId' is not assignable to parameter of type 'UserId'
const orderId = "abc" as OrderId;
getUser(orderId); // Error
```

### When to use

- Entity IDs that must not be confused (`UserId` vs `OrderId` vs `ProductId`)
- Units of measurement (`Milliseconds` vs `Seconds`)
- Validated strings (`Email`, `Url`, `NonEmptyString`)

## Result Type

Replace throw/catch with explicit success/failure return types.

```ts
type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };

function ok<T>(data: T): Result<T, never> {
  return { success: true, data };
}

function err<E>(error: E): Result<never, E> {
  return { success: false, error };
}
```

### Usage in services

```ts
async function createUser(input: CreateUserInput): Promise<Result<User, UserAlreadyExistsError>> {
  const existing = await userRepo.findByEmail(input.email);
  if (existing) {
    return err(new UserAlreadyExistsError(input.email));
  }
  const user = await userRepo.create(input);
  return ok(user);
}
```

### When to use

- Service methods that can fail in **domain-meaningful** ways
- When callers need to handle different error types differently
- Prefer over throwing when the failure is expected (not exceptional)

## Discriminated Unions

Model states that are mutually exclusive.

```ts
type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: AppError };

type PaymentStatus =
  | { type: "pending"; createdAt: Date }
  | { type: "processing"; transactionId: string }
  | { type: "completed"; transactionId: string; completedAt: Date }
  | { type: "failed"; transactionId: string; reason: string };
```

### When to use

- Entity states with different associated data per state
- Event types in event-driven architectures
- API response variants

## Zod Schema Inference

Define the schema once, infer the TypeScript type.

```ts
import { z } from "zod";

const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(100),
  role: z.enum(["admin", "user", "viewer"]),
});

type CreateUserInput = z.infer<typeof CreateUserSchema>;

// Use in route handler
const input = CreateUserSchema.parse(req.body);
```

### Composing schemas

```ts
const BaseEntitySchema = z.object({
  id: z.string().uuid(),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
});

const UserSchema = BaseEntitySchema.extend({
  email: z.string().email(),
  name: z.string(),
});

type User = z.infer<typeof UserSchema>;
```

## Const Assertions

Use `as const` for literal types and readonly tuples.

```ts
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"] as const;
type HttpMethod = (typeof HTTP_METHODS)[number]; // "GET" | "POST" | "PUT" | "DELETE" | "PATCH"

const ERROR_CODES = {
  NOT_FOUND: "NOT_FOUND",
  VALIDATION_ERROR: "VALIDATION_ERROR",
  UNAUTHORIZED: "UNAUTHORIZED",
  CONFLICT: "CONFLICT",
} as const;
type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];
```

## `satisfies` Operator

Validate that a value matches a type without widening.

```ts
type RouteConfig = {
  path: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  auth: boolean;
};

const routes = {
  getUsers: { path: "/users", method: "GET", auth: true },
  createUser: { path: "/users", method: "POST", auth: true },
} satisfies Record<string, RouteConfig>;

// routes.getUsers.method is still "GET" (literal), not string
```

## Mapped Types

Create types derived from other types.

```ts
// Make all properties optional for partial updates
type UpdateUserInput = Partial<Pick<User, "name" | "email" | "role">>;

// Read-only version for responses
type UserResponse = Readonly<Omit<User, "passwordHash">>;

// Map entity to its creation input
type CreateInput<T> = Omit<T, "id" | "createdAt" | "updatedAt">;
```

## Type Guards

Narrow types safely at runtime.

```ts
function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}

function isNotNullish<T>(value: T | null | undefined): value is T {
  return value != null;
}

// Filter with type narrowing
const validUsers = users.filter(isNotNullish);
```

### Assertion functions

```ts
function assertDefined<T>(value: T | null | undefined, message: string): asserts value is T {
  if (value == null) {
    throw new InternalError(message);
  }
}
```

## Generic Constraints

Constrain generics to ensure type safety.

```ts
interface Repository<T extends { id: string }> {
  findById(id: string): Promise<T | null>;
  create(data: Omit<T, "id">): Promise<T>;
  update(id: string, data: Partial<T>): Promise<T>;
  delete(id: string): Promise<void>;
}
```

## What to Avoid

- `any` — use `unknown` and narrow, or proper generics
- Type assertions (`as`) unless unavoidable — prefer type guards
- `Enum` when `as const` objects or union types suffice (enums have runtime quirks)
- Overusing utility types — if the derived type is hard to read, define it explicitly
- `@ts-ignore` or `@ts-expect-error` without a tracking issue
