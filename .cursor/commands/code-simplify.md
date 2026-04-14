# Code Simplify — Refactor Without Changing Behavior

Reduce complexity in existing code while preserving exact behavior. Activates the `code-simplification` discipline plus the relevant execution skill.

**This command activates the `code-simplification` skill.** Load `.cursor/skills/code-simplification/SKILL.md`.

In addition to the process skill, load the execution skill that owns the code being simplified:

| Code being simplified | Execution skill to load |
|---|---|
| Backend TypeScript | `backend-ts-expert` |
| Backend Python | `backend-py-expert` |
| Frontend TypeScript | `frontend-ts-expert` |
| Infrastructure / IaC | `devops-aws-expert` |

## What the skill enforces

- **Chesterton's Fence** — understand why the code exists before changing it. If you cannot explain the existing design, you cannot simplify it.
- **Behavior preservation** — refactoring is by definition behavior-preserving. Behavior changes are features (`/build`) or bug fixes (`/debug`).
- **Test before AND after** — the test suite is the safety net. If tests are missing, write characterization tests **first** as a separate commit.
- **One simplification per commit** — never bundle.
- **Stay strictly in scope** — adjacent code is noted for follow-up, not refactored in this task.

## The 7-step refactoring cycle

```
Understand → Identify → Plan → Test before → Refactor → Test after → Commit
```

Each cycle ends with one commit. If multiple simplifications are needed, repeat the cycle for each.

## What /code-simplify never does

- **Never** changes behavior (that is `/build` or `/debug`)
- **Never** bundles multiple refactors in one commit
- **Never** refactors code the agent does not understand
- **Never** refactors untested code without first writing characterization tests
- **Never** edits a failing test to make it match the refactor (the failure means behavior changed — revert)
- **Never** deletes a test
- **Never** adds a dependency to enable the simplification
- **Never** auto-commits — defer to `commit-manager`

## Common refactors this skill enables

- Extract function (decompose long functions)
- Extract constant (replace magic numbers and repeated literals)
- Rename for clarity (variables, functions, classes — Ask First for public API)
- Replace deep nesting with early returns / guard clauses
- Replace boolean parameter with two functions
- Group related parameters into a struct/object/dataclass
- Remove dead code (Ask First — verify with grep + git history)
- Replace duplicated blocks with a parameterized helper (when ≥3 callers)

## Suggested next steps after /code-simplify

- To validate behavior preservation → run the execution skill's full Verification (already enforced by the skill)
- To commit each refactor → `/commit-files` (commit-manager) — one commit per simplification
- If multiple simplifications are needed → run `/code-simplify` again for each
- If the simplification reveals an architectural issue → `/decide` to record a `DEC-NNN`
- If a regression surfaces during the refactor → revert and `/debug`
