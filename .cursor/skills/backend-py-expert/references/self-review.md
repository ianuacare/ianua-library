# Backend Python — Self-Review Lens

This file is the self-review lens for `backend-py-expert`. Loaded on demand at step 7 of the Execution Workflow. Three tools to use before declaring "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation
2. **Red Flags** — observable signals in the diff, behavior, and runtime
3. **Ask First decision aids** — concrete examples that disambiguate the most fragile boundary tier

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's just a quick endpoint, I'll skip the Pydantic schema." | The first time it receives malformed input in production, it raises a 500 or corrupts data. The schema takes 30 seconds to write. |
| "I'll add tests after the feature works." | "After" never comes. Tests written after the fact tend to confirm the implementation, not the requirements. Write tests alongside the code. |
| "Coverage 80% is arbitrary, this code is simple enough." | Simple code has bugs too. The 80% threshold exists so the *agent doesn't get to decide* when to skip tests. |
| "I'll use `Any` here, the type is too complex." | If the type is too complex to write, the data shape is too complex to reason about. `object` + isinstance narrowing or a Protocol forces you to think. |
| "The framework's default is fine, I don't need to look at the docs." | The default may be fine — but you don't know that until you've read the docs. |
| "I'll use `print()` for now and switch later." | "Later" is never. The structlog call takes the same number of keystrokes. |
| "It's faster to raise a generic Exception and handle it at the top level." | A generic exception loses context. You can't distinguish "user not found" from "database down" at the top level. |
| "I'll write the API docs after the endpoint is stable." | The endpoint is never stable. Let FastAPI generate OpenAPI from the Pydantic models — design the contract via the schema. |
| "The migration is reversible in theory, I don't need to test the downgrade." | Reversible-in-theory migrations bite during incident response at 3am. Run `alembic downgrade -1` locally before merging. |
| "I'll add the env var validation after I get the feature working locally." | The bug you're going to ship is "works on my machine because I have the env var set". Validate at boot via `BaseSettings`, fail fast. |
| "This bug is too small to need a regression test." | Bugs that "look small" recur. Regression tests are the cheapest insurance. |
| "I'll add `# type: ignore` here, mypy is being annoying." | mypy is being precise. The ignore hides a real type mismatch — fix the type, don't silence the checker. |
| "I'll catch and log this exception, it can't really happen." | If it can't happen, the catch is harmless. If it can happen, you've just hidden a real bug behind a log line. |

---

## Red Flags

### In the diff

- A new function added without a corresponding test in the same diff
- A `try: ... except: pass` or `except Exception: pass` block
- A new public function/class with no docstring
- An `Any` type added (even a single one)
- A `# type: ignore` without an inline justification
- A `# TODO: validate this later` comment
- An `await` missing on a coroutine call
- A new endpoint added with no corresponding OpenAPI schema update
- An `os.environ["X"]` direct read bypassing the `BaseSettings` config
- An Alembic migration with no `downgrade()` body
- A new `pip install` of a package not justified in the PR description
- Business logic inside a router/view (FastAPI route function, Django view)
- An f-string used to build SQL

### In the agent's behavior

- The agent says "I'll add tests in a follow-up PR"
- The agent reaches for `Any` instead of asking for type clarification
- The agent introduces a new ORM/framework/library without warning the user
- The agent skips the Verification checklist
- The agent reports "done" without showing test or type-check output
- The agent raises bare `Exception("...")` with a string literal
- The agent silently catches an error during retry logic instead of typing it
- The agent edits files outside the requested scope without asking

### In the running code

- Logs containing raw user input, tokens, or PII
- Logs from `print()` instead of structlog
- HTTP responses leaking stack traces or internal exception messages
- Endpoints returning 500 with no log entry on the server side
- Database queries inside loops (N+1 pattern, missing `selectinload` / `select_related`)
- Long-running transactions wrapping HTTP or external I/O calls
- Health check endpoint missing or returning 200 unconditionally

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Adding `marshmallow` to a project that uses `pydantic` | **Yes** | Replacing the project standard for validation |
| Adding `requests` to a project that uses `httpx` | **Yes** | Replacing the project standard for HTTP |
| Adding a transitive dependency required by an already-installed package | **No** | Not a real choice |
| Adding `types-*` stub packages for an already-used package | **No** | Type-only, non-functional |
| Adding a new file in `services/` following existing patterns | **No** | In-scope, no architectural change |
| Renaming `user_service.py` → `users/service.py` (touches every importer) | **Yes** | Outside requested scope, broad blast radius |
| Renaming a private variable inside one function | **No** | Local refactor, no impact outside the function |
| Adding a new index to an Alembic migration that has been applied | **Yes** | Schema change, requires a new migration |
| Adding a new column to a brand-new table not yet migrated | **No** | Same migration, still in design |
| Adding a new test file alongside existing tests | **No** | Always allowed |
| Switching test runner from pytest to unittest | **Yes** | Project-wide standard change |
| Bumping a dependency patch version | **No** | Routine maintenance, unless explicitly forbidden |
| Bumping a dependency major version | **Yes** | Likely breaking changes |
| Introducing Hexagonal architecture in a layered codebase | **Yes** | New architectural pattern; requires ADR |
| Adding a new mapper layer inside the existing layered architecture | **No** | Within the existing pattern |
| Replacing `print()` with structlog in code the user did not ask to touch | **Yes** | Outside requested scope, even if it improves the code |
| Adding structlog in new code being written right now | **No** | "Always Do" rule applies |
| Adding a new env var read by code being written now | **No** | But `BaseSettings`, `.env.example`, README must all update together |
| Adding a third-party HTTP call in the service being written | **Yes** | New external dependency surface |

### Default rule

If the change is **inside the file or module being actively edited** AND covered by an "Always Do" rule, proceed. Otherwise, when in doubt, ask.
