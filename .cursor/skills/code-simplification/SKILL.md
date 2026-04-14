---
name: code-simplification
description: >-
  Defines the discipline of refactoring code to reduce complexity while preserving exact
  behavior. Activates when the user asks to simplify, refactor, clean up, deduplicate, or
  reduce complexity in existing code that already works. Enforces Chesterton's Fence
  (understand before changing), behavior preservation, test-before-and-after, one
  simplification per commit, and explicit scope boundaries. Do NOT use for adding new features
  (use incremental-implementation), for fixing bugs (use debugging-and-error-recovery), or for
  performance optimization (which may legitimately change behavior).
---

# Code Simplification — Process Skill

## When to Activate

### Activate this skill when:

- The user asks to "simplify", "refactor", "clean up", "deduplicate", or "reduce complexity"
- The user asks to "make this readable", "reorganize", "improve maintainability"
- A code review found unnecessary complexity that the user wants addressed
- The user asks to "extract a function", "split this file", "rename for clarity"
- The `/code-simplify` command is invoked
- During an `incremental-implementation` slice the agent notices adjacent complexity and the user asks to address it as a follow-up

### Do NOT activate for:

- Adding new features → use `incremental-implementation`
- Fixing bugs → use `debugging-and-error-recovery`
- Performance optimization (which may legitimately change behavior) → use the relevant execution skill's performance reference
- Code that does not yet exist (you cannot simplify what is not there)
- Code the agent does not understand (Chesterton's Fence — see Always Do)

## Role: Refactoring Discipline

This skill is the **process backbone** for refactoring. It does not write the new code itself — it dictates the rules under which the execution skill rewrites existing code: understand first, preserve behavior, test before and after, one change per commit.

Three values:

- **Understand before changing** — Chesterton's Fence: do not remove a fence until you know why it was built
- **Behavior preservation** — refactoring is by definition behavior-preserving. Behavior changes are features or bug fixes, not refactoring.
- **Test as the contract** — the test suite is the proof that behavior was preserved. If tests are missing, write them first.

## Operating Boundaries

This skill operates under three explicit boundary tiers. The agent must respect all three. Violations are bugs, not preferences.

### Always Do (no exceptions)

1. **Understand before changing (Chesterton's Fence)** — read the code in scope, read the tests that exercise it, read the commit history (`git log -p`) for non-obvious lines. If you cannot explain *why* a piece of code exists, you cannot simplify it.
2. **Preserve behavior exactly** — public API signatures, return types, error semantics, side effects, ordering, edge cases. Refactoring that changes behavior is forbidden.
3. **Test before and after** — run the existing test suite for the affected code. It must pass before the refactor and after. If tests are missing for the area being refactored, **write them first** as a separate commit (see below).
4. **One simplification per commit** — extract a function, rename a variable, inline a constant — one operation per commit. Never bundle.
5. **Add tests if coverage is missing** — before refactoring untested code, write characterization tests that lock in current behavior. These tests are the safety net.
6. **Stay in scope** — only modify what the user asked to simplify. Adjacent code that "could also be improved" is noted as a follow-up, not refactored.
7. **Use the execution skill's patterns** — refactoring patterns come from the loaded execution skill's `references/<lang>-patterns.md`. This skill governs the *discipline*, the execution skill governs the *patterns*.
8. **Run the execution skill's full Verification** after the refactor.
9. **Document non-obvious removals** — if a piece of code is removed because it was dead, the commit message explains how that was verified.
10. **Suggest the change first if scope is unclear** — present what will be simplified, get user confirmation, then refactor.

### Ask First (requires explicit user confirmation)

1. **Removing seemingly unused code** — code that looks dead may be reflected, dynamically loaded, or used by tooling. Confirm with grep + user.
2. **Renaming a public API** (function, class, exported symbol) — touches every importer.
3. **Restructuring file layout** (moving files, splitting modules, merging modules) — broad blast radius.
4. **Refactoring beyond the explicitly requested scope** — even if it "obviously belongs together".
5. **Introducing a new abstraction** (helper, base class, mixin) — abstractions are decisions, not simplifications.
6. **Changing a name in a way that affects the public docs or API surface.**
7. **Adding a dependency** to enable a simplification (e.g. lodash for a one-liner) — almost always wrong.
8. **Removing a comment that explains a non-obvious choice** — confirm the comment is actually obsolete.
9. **Removing a try/catch** — even if it looks redundant, confirm.
10. **Changing the order of operations** in code with side effects — confirm.

### Never Do (absolute, no override)

1. **Never simplify code you do not understand.**
2. **Never change behavior** while simplifying — that is a feature change or bug fix, route through the appropriate skill.
3. **Never bundle multiple simplifications** into one commit.
4. **Never bundle a simplification with a feature change or a bug fix.**
5. **Never refactor without running the tests before and after.**
6. **Never delete a test** to make a refactor pass.
7. **Never refactor adjacent code "while you're there".**
8. **Never refactor code that has no tests** without first writing characterization tests as a separate commit.
9. **Never auto-commit** — defer to `commit-manager`.
10. **Never push to a remote** — out of scope.
11. **Never simplify generated code, vendor code, or third-party code** — modify the generator or upgrade the dependency instead.
12. **Never add a comment that says "this code was simplified"** — git history does that job; comments explain the *why* of the code, not its history.

### Violation protocol

If you (the agent) realize you have violated or are about to violate any rule above:

1. **Stop.** Do not propose more refactors or run more commands.
2. **Surface the violation.** Tell the user explicitly: which rule, which file, what was done.
3. **Propose a correction** — revert the file, restore the test, narrow the scope.
4. **Wait for user confirmation** before applying.
5. **Do not paper over.** A refactor that changes behavior is a regression in disguise.

## The Refactoring Cycle

The skill's core process is a 7-step sequence per simplification.

```
1. Understand     →  read code, read tests, read history
2. Identify       →  list specific code smells (be concrete)
3. Plan           →  one simplification at a time, smallest first
4. Test before    →  existing tests pass; if missing, add characterization tests first
5. Refactor       →  apply the one planned change
6. Test after     →  same tests still pass
7. Commit         →  via commit-manager, descriptive message
```

### 1. Understand

Read the code in scope. Read the tests that exercise it. Read the git log for non-obvious lines (`git log -p <file>`). For each construct that looks weird, find out *why* before deciding it is unnecessary.

If you cannot answer "why does this exist?" for any non-trivial line, **stop and investigate** before proposing a change.

### 2. Identify code smells

List specific smells you observe. Be concrete; "this is messy" is not a smell. Examples of concrete smells:

- Function longer than ~50 lines
- Function with more than ~5 parameters
- Boolean parameter that controls two distinct behaviors
- Deep nesting (>3 levels)
- Repeated literal value used in many places
- Variable name that doesn't reveal intent (`tmp`, `data`, `x`)
- Comment explaining what the code does (instead of why)
- Dead code (unused import, unreachable branch)
- Two near-duplicate code blocks differing only in a constant
- Name that no longer reflects current behavior
- Type declaration that has drifted from the actual shape

### 3. Plan

Choose **one** simplification to apply. The smallest, safest, most localized one first. Bigger refactors (file splits, abstraction extraction) come later, after the smaller ones have shrunk the scope.

If multiple simplifications are needed, list them in order and apply them one at a time.

### 4. Test before

Run the test suite for the affected code. They must pass.

If tests are **missing or insufficient**:

1. **Stop.** Do not refactor untested code.
2. Write characterization tests that lock in the current behavior — including edge cases.
3. Verify the tests pass against the current code.
4. **Commit the tests as a separate commit** ("test: add characterization tests for X before refactor").
5. *Now* you can refactor.

### 5. Refactor

Apply the one planned change. Stay within the planned scope. If you discover the change requires also modifying adjacent code, **stop and re-plan** — the simplification was not as small as you thought.

### 6. Test after

Run the same test suite. Every test that passed in step 4 must still pass. Run the loaded execution skill's full Verification (type checker, lint, full test suite).

If a test fails, the refactor changed behavior. **Revert and re-plan.** Do not "fix" the test.

### 7. Commit

Suggest committing via `commit-manager`. The commit message follows the template:

```
refactor(<scope>): <one-line description of the simplification>

What changed: <what was simplified, in 1-2 sentences>
Why: <why this simplification is valuable — readability, maintainability, removing duplication>
Behavior preserved: yes (verified by test suite at <commit hash before>)
```

If multiple simplifications are needed, return to step 1 for the next one. Each simplification is its own commit.

## Common Code Smells (with the response)

| Smell | Response |
|---|---|
| Function longer than ~50 lines | Extract sub-function for the most cohesive block |
| Function with >5 parameters | Group related parameters into a struct/object/dataclass |
| Boolean parameter controlling two behaviors | Split into two functions |
| Deep nesting (>3 levels) | Early returns, guard clauses, extract sub-function |
| Repeated literal | Extract a named constant |
| Two near-duplicate blocks | Extract a function with the differing values as parameters |
| Comment explaining *what* the code does | Rename or extract; the code should explain itself |
| Comment explaining *why* | Keep — comments explain why, not what |
| Dead code | Verify with grep + git history, then remove (Ask First) |
| `tmp`, `data`, `x` variable names | Rename to intention-revealing names |
| Drifted type | Update the type to match current usage; verify with type checker |
| Import not used | Remove |
| Unreachable branch | Remove (after confirming it is truly unreachable) |

## Verification

This skill's verification is **process-based**: it checks that the discipline was followed.

### Mandatory checks (every simplification)

- [ ] The agent can explain *why* the original code existed (Chesterton's Fence applied).
- [ ] Tests for the affected code passed before the refactor.
- [ ] If tests were missing, characterization tests were added in a separate commit first.
- [ ] Exactly one simplification was applied in the commit.
- [ ] Tests still pass after the refactor.
- [ ] The execution skill's full Verification ran and passed.
- [ ] No public API signature changed (or, if it did, Ask First was confirmed and downstream impact noted).
- [ ] No behavior changed.
- [ ] The commit message follows the refactor template (what / why / behavior preserved).

### Conditional checks

If the simplification **removed code**:
- [ ] Removal was verified with a project-wide search (`grep` / IDE references).
- [ ] No reflection, dynamic dispatch, or external tooling depends on the removed code.
- [ ] Removal was confirmed via Ask First.

If the simplification **renamed a public symbol**:
- [ ] All importers were updated in the same commit.
- [ ] Documentation references were updated.
- [ ] CHANGELOG entry added if the symbol is part of a published API.

If the simplification **extracted a new abstraction**:
- [ ] The abstraction has at least 2 callers (otherwise it is premature).
- [ ] The abstraction was confirmed via Ask First.

### Disqualifying signals (block "done")

- A refactor on code the agent could not explain
- A test failure ignored or "fixed" instead of investigated
- Multiple simplifications bundled into one commit
- A simplification bundled with a feature change or bug fix
- A test deleted or disabled
- Adjacent unrelated code modified
- Refactoring of untested code without prior characterization tests
- A new abstraction with only one caller
- A dependency added "to enable" the simplification

## Self-Review

The self-review lens for this skill — Common Rationalizations, Red Flags, and Ask First decision aids — lives in `references/self-review.md`. Loaded on demand at the end of every simplification. Do not skip it.

## Integration with Other Skills

### Execution skills (`backend-ts-expert`, `backend-py-expert`, `frontend-ts-expert`, `devops-aws-expert`)

This skill is the **process layer** for refactoring. The execution skill provides language- and framework-specific patterns from its `references/<lang>-patterns.md`. This skill provides the discipline. Both must be loaded together.

### `incremental-implementation`

These two skills are mutually exclusive in a single commit:

- `incremental-implementation` adds new behavior in slices
- `code-simplification` preserves behavior while reducing complexity

If during a slice the agent notices adjacent complexity, it must **not** simplify in the slice. Note it as a follow-up `/code-simplify` task. After the slice is committed, return separately.

### `debugging-and-error-recovery`

If a fix reveals that the surrounding code is too complex to reason about, suggest a follow-up `/code-simplify` task **after** the fix is committed. Never refactor in the fix commit.

### `commit-manager`

Each simplification is its own commit, suggested via `commit-manager`. The message uses the `refactor(<scope>):` prefix.

### `pm-github-workflow`

If the simplification work has a tracking issue, reference it via `Refs: #N`. For larger simplification efforts (file splits, dead code removal sweeps), suggest creating a tracking issue first.

### `decision-log-patterns` and domain skills

If the simplification reveals an architectural weakness or proposes a structural change that goes beyond a single file, suggest writing a `DEC-NNN` (or domain-specific decision record) before refactoring further.

## Bundled Resources

```
code-simplification/
├── SKILL.md
└── references/
    └── self-review.md       # loaded at the end of every simplification
```
