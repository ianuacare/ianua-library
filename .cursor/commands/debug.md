# Debug — Triage and Fix a Failure

Triage a failing test, broken build, error, exception, or unexpected behavior using the 5-step process: reproduce, localize, reduce, fix, guard.

**This command activates the `debugging-and-error-recovery` skill.** Load `.cursor/skills/debugging-and-error-recovery/SKILL.md`.

In addition to the process skill, load the execution skill that owns the affected code:

| Affected area | Execution skill to load |
|---|---|
| Backend TypeScript code | `backend-ts-expert` |
| Backend Python code | `backend-py-expert` |
| Frontend TypeScript code | `frontend-ts-expert` |
| Infrastructure / IaC / Docker / CI | `devops-aws-expert` |
| Failing E2E scenario | `e2e-tester` (re-validation mode) |

## What the skill enforces

- **Reproduce first** — never fix what you cannot reproduce
- **Localize before fixing** — narrow to the smallest possible scope
- **Reduce** — minimal failing test case becomes the regression test
- **Fix root cause, not symptom**
- **Guard** — every bug becomes a permanent regression test

## Stop-the-line triggers

These conditions suspend other work and become the only priority:

- Production incident
- Data loss or corruption risk
- Security vulnerability
- CI red on main for >30 min
- Build broken on the user's machine

## What /debug never does

- **Never** modifies production data without Ask First confirmation
- **Never** disables or deletes a test to bypass the bug
- **Never** wraps the failure in `try { ... } catch {}` to silence it
- **Never** declares "fixed" without re-running the failing test
- **Never** bundles the fix with adjacent refactoring or feature changes
- **Never** auto-commits — defer to `commit-manager`

## Suggested next steps after /debug

- To re-validate via E2E → `/test` (e2e-tester) in re-validate mode
- To commit the fix and the regression test → `/commit-files` (commit-manager)
- If the bug points to architectural weakness → `/decide` (record a `DEC-NNN` or domain-specific decision)
- If the surrounding code is too complex to reason about → `/code-simplify` as a follow-up
- To update the issue status → `pm-github-workflow` (suggest)
