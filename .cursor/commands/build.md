# Build — Implement the Task Incrementally

Implement the requested task using the **process layer** (`incremental-implementation`) plus the appropriate execution skill. The two work together: the process skill enforces the increment cycle (plan → implement → test → verify → commit, repeat), and the execution skill provides domain expertise.

## Always load `incremental-implementation` first

Load `.cursor/skills/incremental-implementation/SKILL.md` at the start of every `/build` invocation. It defines the cycle, the scope discipline, the feature flag enforcement, and the commit rhythm. The execution skill is loaded **on top of** it.

## Skill selection (auto-detect)

Inspect the user request, the file paths involved, and the project manifest to choose:

| Signal | Skill to load |
|---|---|
| `package.json` + backend keywords (route, controller, service, ORM, API endpoint) | `backend-ts-expert` |
| `pyproject.toml` / `requirements.txt` + backend keywords | `backend-py-expert` |
| `package.json` + frontend keywords (component, page, hook, JSX, TSX, styling) | `frontend-ts-expert` |
| `*.tf`, `cdk.json`, `Dockerfile`, `.github/workflows/`, infrastructure keywords | `devops-aws-expert` |

If the request spans multiple domains (e.g. "add an API endpoint and the form that calls it"), load the relevant execution skills in sequence — first the backend, then the frontend — and follow each skill's Operating Boundaries independently. The `incremental-implementation` cycle wraps each domain's work.

If the project context is ambiguous, ask the user which skill to use before proceeding.

## How the two skills compose

| Concern | `incremental-implementation` | Execution skill |
|---|---|---|
| **Cycle** (plan → implement → test → verify → commit) | Owns it | Follows it |
| **Slice size and decomposition** | Owns it | N/A |
| **Feature flag enforcement** | Owns it | N/A |
| **Scope discipline** ("don't touch what wasn't asked") | Owns it | Follows it |
| **Language patterns, framework idioms** | N/A | Owns it |
| **Type checker, test runner, lint commands** | N/A | Owns it |
| **Domain Verification** (coverage, security, infra plans) | N/A | Owns it |
| **Decision records** when an architectural choice is made | N/A | Delegated to `decision-log-patterns` via the execution skill |

When the two conflict, the stricter rule wins. (In practice they almost never conflict.)

## What every execution skill enforces

- **Operating Boundaries** (Always Do / Ask First / Never Do)
- **Verification** with tool availability checks, mandatory + conditional checks, and disqualifying signals
- **Self-review** loaded from `references/self-review.md` before declaring "done"
- **Decision records** via `decision-log-patterns` when an architectural choice is made

## What `incremental-implementation` enforces on top

- **Plan the slice in writing** before any code
- **One slice per commit**, no bundling
- **Working code at every checkpoint**
- **Stay strictly in scope** — no "while I'm here" refactors (those go to `/code-simplify`) and no "while I'm here" bug fixes (those go to `/debug`)
- **Suggest decomposition** when a slice exceeds ~200 lines or ~5 files
- **Feature flag every new public surface** by default

## Suggested next steps after /build

- To validate end-to-end → `/test` (e2e-tester)
- To review the diff → `/review`
- To commit → `/commit-files` (commit-manager) — never auto-commit
- To track → `pm-github-workflow` (suggest, the user decides)
- If a bug surfaced during the build → `/debug` (debugging-and-error-recovery), as a separate slice
- If complexity surfaced and the user wants it addressed → `/code-simplify` (code-simplification), as a separate task
