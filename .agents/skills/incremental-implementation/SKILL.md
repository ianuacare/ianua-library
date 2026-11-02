---
name: incremental-implementation
description: >-
  Defines the discipline of building software in thin vertical slices: implement, test, verify,
  commit, repeat. Activates whenever a non-trivial implementation task starts — usually in
  combination with an execution skill (backend-rails-expert, backend-ts-expert, backend-py-expert,
  frontend-ts-expert, devops-aws-expert). Enforces small steps, working code at every checkpoint, feature flags for
  new public surfaces, scope discipline, and rollback-friendly history. Do NOT use for trivial
  one-line fixes (commit them directly), for facilitator tasks (PRDs, wireframes, audits), or
  for pure refactoring (use code-simplification).
---

# Incremental Implementation — Process Skill

## When to Activate

### Activate this skill when:

- A non-trivial implementation task starts (anything sized S or larger per `pm-github-workflow`)
- The user asks to "build", "implement", "add", or "develop" a feature
- An execution skill (`backend-rails-expert`, `backend-ts-expert`, `backend-py-expert`, `frontend-ts-expert`, `devops-aws-expert`) is loaded for new work
- The user explicitly asks to "do this incrementally" or "in small steps"
- The `/build` command is invoked

This skill is **process layer** — it runs in combination with an execution skill (which provides domain expertise) and shapes how that skill writes code.

### Do NOT activate for:

- Trivial one-line fixes (typos, single config changes) → commit directly
- Facilitator tasks (PRDs, wireframes, audits) → use the relevant facilitator skill
- Pure refactoring with no new behavior → use `code-simplification`
- Bug investigation (where the work is to find the cause, not to add a feature) → use `debugging-and-error-recovery`

## Role: Increment Discipline

This skill is the **process backbone** for implementation work. It does not write code itself — it dictates the rhythm at which the execution skill writes code: small slice → test → verify → commit → next slice.

The skill enforces three values:

- **Working code at every checkpoint** — the build never breaks for more than the duration of one slice
- **Reversibility** — every checkpoint is a save point you can revert to
- **Scope discipline** — only what was asked, nothing more

## Operating Boundaries

This skill operates under three explicit boundary tiers. The agent must respect all three. Violations are bugs, not preferences.

### Always Do (no exceptions)

1. **Vertical slicing** — every slice delivers a thin, end-to-end piece of functionality (e.g. one endpoint with its handler, service, repository, validation, and one happy-path test). Never split horizontally (e.g. "all repositories first, then all services").
2. **One increment cycle per slice** — Plan the slice → Implement → Test → Verify → Commit. No skipping steps. No batching commits.
3. **Working code after every slice** — type checker, build, and existing tests all pass at the end of each slice. The branch is never left red overnight.
4. **Test the slice in the same step that implements it** — happy path at minimum. Edge cases and error paths follow in subsequent slices if they grow the surface.
5. **Commit after each green slice** — atomic, descriptive Conventional Commit. Never bundle multiple slices.
6. **Feature flag every new public surface** — new routes, new pages, new exposed APIs default OFF. Toggle ON only on user confirmation.
7. **Rollback-friendly** — every commit can be reverted on its own without breaking the previous commit's slice.
8. **Stay in scope** — only modify what the slice requires. Pre-existing issues found in adjacent code are noted but not fixed in this slice.
9. **Suggest decomposition** when a planned slice is larger than ~200 lines of net diff or touches more than ~5 files. Propose splitting before implementing.
10. **Defer to the execution skill** for all language-, framework-, and domain-specific decisions. This skill governs the *cycle*, the execution skill governs the *content*.

### Ask First (requires explicit user confirmation)

1. **Enlarging the planned scope** of a slice mid-implementation — confirm the new scope or split into a follow-up slice.
2. **Skipping a feature flag** for a new public surface — explain why, get go-ahead.
3. **Removing a feature flag** that was previously toggled OFF — confirm the rollout decision.
4. **Committing on a temporarily red build** because the next slice will fix it — confirm the user accepts the gap.
5. **Touching files outside the slice's planned files** — confirm scope expansion.
6. **Reordering planned slices** when the user has agreed an order.
7. **Skipping the slice plan** ("just go") — confirm and document why.
8. **Creating more than ~3 commits in one go** without user review.

### Never Do (absolute, no override)

1. **Never commit on a broken build** — type checker errors, lint errors, or test failures block the commit.
2. **Never bundle multiple slices into one commit.**
3. **Never refactor unrelated code** "while you're there" — it pollutes the diff.
4. **Never skip the test in a slice** because "the next slice will add it".
5. **Never disable a test** to make a slice green.
6. **Never delete a test** that protects existing behavior.
7. **Never push to a remote** — defer to `commit-manager`.
8. **Never declare "done" without running the full Verification** of the loaded execution skill.
9. **Never start a new slice while the previous one is uncommitted.**
10. **Never skip the feature flag** for a new user-visible page or endpoint.

### Violation protocol

If you (the agent) realize you have violated or are about to violate any rule above:

1. **Stop.** Do not start the next slice.
2. **Surface the violation.** Tell the user explicitly: which rule, which slice, what was done.
3. **Propose a correction** — split the bundled commit, restore the test, narrow the scope.
4. **Wait for user confirmation** before applying.
5. **Do not paper over.** A broken increment cycle defeats the whole point of this skill.

## The Increment Cycle

The skill's core process is a 5-step loop, repeated until the task is complete.

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ┌─────┐    ┌─────────┐    ┌──────┐    ┌────────┐      │
│  │Plan │───→│Implement│───→│ Test │───→│ Verify │      │
│  └─────┘    └─────────┘    └──────┘    └────────┘      │
│     ↑                                        │          │
│     │                                        ↓          │
│     │                                  ┌──────────┐    │
│     └──────────────────────────────────│  Commit  │    │
│                                        └──────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1. Plan the slice

Before writing any code:

- State explicitly what this slice delivers in 1 sentence.
- List the files the slice will touch (target: ≤5 files).
- List the test that will prove the slice works.
- If the slice is larger than ~200 lines of net diff, **stop and propose splitting**.

### 2. Implement

Write the code following the loaded execution skill's guidance. Stay within the planned files. If you discover the slice needs to expand, return to step 1 (do not silently grow).

### 3. Test

Write the test that proves the slice works. Run it. Verify it fails before the implementation is complete (red), then passes (green).

For execution skills with coverage requirements (`backend-*`, `frontend-ts-expert`), the slice's test contributes to the ≥80% coverage threshold defined in the execution skill's Verification.

### 4. Verify

Run the loaded execution skill's **Mandatory checks** (type checker, full test suite, linter). They must all pass before commit.

### 5. Commit

Use `commit-manager` for the commit. Suggest, do not auto-commit. The commit message follows Conventional Commits, with a scope from the slice's domain.

After commit, return to step 1 for the next slice.

## Decomposition Heuristics

When the user describes a task, decompose it into vertical slices using these heuristics.

### Backend feature ("add a new endpoint")

1. **Slice 1** — Schema + types + 1 happy-path test (no handler yet, just the contract)
2. **Slice 2** — Repository + repository test
3. **Slice 3** — Service + service test
4. **Slice 4** — Handler + integration test
5. **Slice 5** — Wire-up (routes, DI, config) + smoke test
6. **Slice 6** — Edge cases and error paths
7. **Slice 7** — Documentation (OpenAPI, README, ADR if architectural)

### Rails feature ("add a backoffice resource")

1. **Slice 1** — Migration + model (validations, associations, scopes) + model spec
2. **Slice 2** — Service (business logic) + service spec
3. **Slice 3** — Policy (authorization rules, relation_scope) + policy spec
4. **Slice 4** — Controller + routes + request spec
5. **Slice 5** — Views (Slim) + components + i18n keys
6. **Slice 6** — Edge cases, error paths, Turbo interactions
7. **Slice 7** — Documentation (OpenAPI if API, architecture docs if needed)

### Frontend feature ("add a new page")

1. **Slice 1** — Static layout (default state) + render test
2. **Slice 2** — Loading state + test
3. **Slice 3** — Empty state + test
4. **Slice 4** — Error state + test
5. **Slice 5** — Data fetching wired up + integration test
6. **Slice 6** — Interactions (forms, navigation) + test
7. **Slice 7** — Accessibility polish (focus, ARIA, keyboard) + manual walk
8. **Slice 8** — Responsive breakpoints

### Infrastructure change ("add a new RDS instance")

1. **Slice 1** — Networking (subnets, security groups) + plan review
2. **Slice 2** — Parameter group + KMS key
3. **Slice 3** — RDS instance (private, encrypted, multi-AZ) + plan review
4. **Slice 4** — CloudWatch alarms + dashboard
5. **Slice 5** — Backup policy + verification
6. **Slice 6** — Runbook + ADR (`INFRA-NNN`)

These are templates, not laws. Adapt to the actual task.

## Verification

This skill's verification is **process-based**: it checks that the cycle was followed, not the code itself (the loaded execution skill checks the code).

### Mandatory checks (every slice)

- [ ] The slice was planned in writing (1-sentence delivery + file list + test name) before implementation started.
- [ ] The implementation stayed within the planned files (or scope expansion was confirmed).
- [ ] The test was written and runs as part of this slice.
- [ ] The execution skill's Mandatory checks (type checker, test suite, linter) all passed before commit.
- [ ] The commit message follows Conventional Commits and references the slice content accurately.
- [ ] No previously-passing test is now failing.

### Mandatory checks (every task, on completion)

- [ ] The task was decomposed into ≥2 slices (or the task was so small that 1 slice was justified, with explicit note).
- [ ] Every slice ended in a green commit.
- [ ] The full execution skill's Verification (Mandatory + Conditional + Disqualifying) passed at the end.
- [ ] No commit was made on a temporarily-red build (or, if Ask-First-confirmed, the gap is documented).
- [ ] Feature flag toggles state matches the user's confirmation.

### Disqualifying signals (block "done")

- A commit on a red build that was not Ask-First-confirmed
- Two slices bundled into one commit
- A test deleted or disabled to make a slice pass
- Files modified outside the planned slice without scope confirmation
- A new public surface without a feature flag (and without Ask-First confirmation to skip it)
- A slice >200 lines that was not proposed for splitting
- The execution skill's Verification not run at the end

## Self-Review

The self-review lens for this skill — Common Rationalizations, Red Flags, and Ask First decision aids — lives in `references/self-review.md`. Loaded on demand at the end of every slice and at task completion. Do not skip it.

## Integration with Other Skills

### Execution skills (`backend-rails-expert`, `backend-ts-expert`, `backend-py-expert`, `frontend-ts-expert`, `devops-aws-expert`)

This skill is the **process layer** that wraps execution. It runs concurrently with whichever execution skill applies to the task. The execution skill provides:

- Language-specific patterns
- Framework conventions
- Domain-specific Verification (tool runners, coverage, security scans)

This skill provides:

- The increment cycle
- Scope discipline
- Atomic commit rhythm
- Feature flag enforcement

When both are loaded, this skill defines the *cycle* and the execution skill defines the *content*. Conflicts are rare; when they happen, the stricter rule wins.

### `commit-manager`

After every green slice, suggest committing via `commit-manager`. Never auto-commit. This skill drives the commit rhythm; `commit-manager` executes the commit.

### `e2e-tester`

Once the task is complete, suggest running the relevant E2E suite via `e2e-tester` to validate the slices integrate correctly.

### `pm-github-workflow`

When a task starts, suggest tracking it as an issue via `pm-github-workflow`. Reference the issue in slice commit messages via `Refs: #N`. Never auto-create issues.

### `code-simplification`

If, during a slice, the agent notices that adjacent code is hard to understand, do **not** refactor it in the slice. Suggest a follow-up `/code-simplify` task instead. Mixing simplification with new feature work is forbidden.

### `debugging-and-error-recovery`

If a slice fails because of an existing bug (not a bug introduced by the slice), suspend the slice, switch to `debugging-and-error-recovery`, fix the bug as a separate slice, then resume.

## Bundled Resources

```
incremental-implementation/
├── SKILL.md
└── references/
    └── self-review.md       # loaded after every slice and at task completion
```
