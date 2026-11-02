# Backend TypeScript — Self-Review Lens

This file is the **self-review lens** for the `backend-ts-expert` skill. It is loaded on demand, not on every invocation. It contains three tools the agent must use before declaring an implementation task "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation. If the agent finds itself thinking one of these, it must stop and reconsider.
2. **Red Flags** — observable signals in the diff, in the agent's own behavior, and in the running code. Used to detect violations after they occur.
3. **Ask First decision aids** — concrete examples that disambiguate the most fragile tier of Operating Boundaries.

This file is referenced from the main `SKILL.md` workflow at step 7 (Self-review). The agent must load and apply it before reporting done.

---

## Common Rationalizations

The following are excuses agents (and humans) use to skip steps in this skill. None of them are valid. If you find yourself thinking one of these, stop and follow the skill instead.

| Rationalization | Reality |
|---|---|
| "It's just a quick endpoint, I'll skip the Zod schema." | The first time it receives malformed input in production, it crashes or corrupts data. The schema takes 30 seconds to write. |
| "I'll add tests after the feature works." | "After" never comes. Tests written after the fact tend to confirm the implementation, not the requirements. Write tests alongside the code. |
| "Coverage 80% is arbitrary, this code is simple enough." | Simple code has bugs too — arguably more often, because nobody scrutinized it. The 80% threshold exists so the *agent doesn't get to decide* when to skip tests. |
| "I'll use `any` here, the type is too complex." | If the type is too complex to write, the data shape is too complex to reason about. `unknown` + narrowing forces you to think about the actual cases. |
| "The framework's default is fine, I don't need to look at the docs." | The default may be fine — but you don't know that until you've read the docs. "I assumed" is the most expensive sentence in software. |
| "I'll log this with `console.log` for now and switch later." | "Later" is never. The Pino call takes the same number of keystrokes. |
| "It's faster to throw a generic Error and handle it at the top level." | A generic Error loses context. You can't distinguish "user not found" from "database down" at the top level, and your error response will be wrong. |
| "I'll write the API docs after the endpoint is stable." | The endpoint is never stable. Write the OpenAPI spec first — it forces you to design the contract before the implementation. |
| "The migration is reversible in theory, I don't need to test the down step." | Reversible-in-theory migrations bite during incident response at 3am. Run the down step locally before merging. |
| "I'll add the env var validation after I get the feature working locally." | The bug you're going to ship is "works on my machine because I have the env var set". Validate at boot, fail fast. |
| "This bug is too small to need a regression test." | Bugs that "look small" recur. Regression tests are the cheapest insurance in software. |
| "This is a refactor, I don't need to update the documentation." | Refactors that change names, file paths, or call signatures **are** documentation changes. Update them or future-you will be confused. |
| "I'll catch and ignore this error, it can't really happen." | If it can't happen, it won't fire and the catch is harmless. If it can happen, you've just hidden a real bug. Either way, type the error and handle it explicitly. |

---

## Red Flags

Observable patterns that indicate this skill is being violated. Watch for these during self-review and during code review of work produced under this skill.

### In the diff

- A new function added without a corresponding test in the same diff
- A `try { ... } catch {}` block with an empty or `console.log`-only catch
- A new public function with no JSDoc/TSDoc
- An `any` type added (even a single one)
- A `// @ts-ignore` or `// @ts-expect-error` without an inline justification
- A `// TODO: validate this later` comment
- A floating promise: `someAsyncFn()` not `await someAsyncFn()`
- A new endpoint added with no corresponding OpenAPI spec change
- A new env var read with `process.env.X` directly (bypassing the validated config)
- A migration with no down step
- An `npm install` of a package not justified in the PR description
- Business logic inside a controller/route handler

### In the agent's behavior

- The agent says "I'll add tests in a follow-up PR"
- The agent reaches for `any` instead of asking for type clarification
- The agent introduces a new ORM/framework/library without warning the user
- The agent skips the Verification checklist
- The agent reports "done" without showing test or type-check output
- The agent uses `throw new Error("...")` with a string literal
- The agent silently catches an error during retry logic instead of typing it
- The agent edits files outside the requested scope without asking

### In the running code

- Logs containing raw user input, tokens, or PII
- Logs from `console.log` instead of the structured logger
- HTTP responses leaking stack traces or internal error messages
- Endpoints returning 500 with no log entry on the server side
- Database queries inside loops (N+1 pattern)
- Long-running transactions wrapping I/O calls
- Health check endpoint missing or returning 200 unconditionally

---

## Ask First — decision aids

The "Ask First" tier in Operating Boundaries is the most fragile because it requires recognizing a fuzzy boundary. Use the table below to disambiguate. When in real doubt, default to asking — false positives cost a question, false negatives cost trust.

### Disambiguation table

| Situation | Ask First? | Why |
|---|---|---|
| Adding `io-ts` to a project that already uses `zod` | **Yes** | Replacing the project standard for validation |
| Adding `lodash` to a project that already uses `radash` | **Yes** | Replacing the project standard for utilities |
| Adding a peer dependency that an already-installed package requires | **No** | Transitive, no real choice |
| Adding `@types/*` for a package already used | **No** | Non-functional, type-only |
| Adding a new file in `services/` following existing patterns | **No** | In-scope, no architectural change |
| Renaming `userService.ts` → `user.service.ts` (touches every importer) | **Yes** | Outside requested scope; broad blast radius |
| Renaming a private variable inside one function | **No** | Local refactor, no impact outside the function |
| Adding a new index to an existing migration that has been applied | **Yes** | Schema change, requires a new migration |
| Adding a new column with a default value to a brand-new table not yet migrated | **No** | Same migration, still in design |
| Adding a new test file alongside existing tests | **No** | Always allowed |
| Switching test runner from Vitest to Jest | **Yes** | Project-wide standard change |
| Bumping a dependency patch version (e.g. `1.2.3` → `1.2.4`) | **No** | Routine maintenance, unless explicitly forbidden by config |
| Bumping a dependency major version | **Yes** | Likely breaking changes |
| Introducing Hexagonal architecture in a layered codebase | **Yes** | New architectural pattern; requires ADR |
| Adding a new layer (e.g. mapper) inside the existing layered architecture | **No** | Within the existing pattern |
| Replacing `console.log` with Pino in code the user did not ask to touch | **Yes** | Outside requested scope, even if it improves the code |
| Adding Pino in new code being written right now | **No** | "Always Do" rule applies |
| Adding a new env var read by code being written right now | **No** | But the env schema, `.env.example`, and README must all be updated together |
| Adding a third-party HTTP call in the service being written | **Yes** | New external dependency surface; affects testing, observability, error handling |

### Default rule

If the change is **inside the file or module being actively edited** AND covered by an "Always Do" rule, proceed. Otherwise, when in doubt, ask.
