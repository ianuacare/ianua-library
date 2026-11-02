---
name: commit-manager
description: >-
  Splits working tree changes into meaningful Conventional Commits grouped by
  topic. Activates ONLY on explicit user request ("commit", "committa",
  "fai il commit", "/commit-files"). Do NOT auto-commit after completing
  any task. Do NOT push.
---

# Commit Manager

## When to Activate

### Activate this skill when the user:

- Explicitly asks to commit changes (e.g., "commit", "committa", "fai il commit", "commit the changes")
- Uses the `/commit-files` command
- Asks to split or organize changes into commits

### **Do NOT activate:**

- **After completing a feature, fix, refactor, or any other task** — wait for the user to explicitly request a commit
- When the user asks to push code (push is out of scope)
- When the user asks to amend a commit without specifying which one

## Operating Boundaries

This skill operates under three explicit boundary tiers. Commit operations touch git history (shared state) so the rules are strict.

### Always Do (no exceptions)

1. **Activate only on explicit user request** — "commit", "committa", "/commit-files". Never on task completion.
2. **Conventional Commits format** — `<type>(<scope>): <subject>` for every commit.
3. **Group changes by topic** — never one giant commit. Split by file purpose using path heuristics.
4. **Verify pre-commit checks** before starting (in repo, no rebase/merge in progress, changes exist).
5. **Stage explicitly** — `git add <specific files>`, never `git add .` or `git add -A`.
6. **Use the registered commit order** — defaults from the workflow, override only via `commit-config.json`.
7. **Run pre-commit hooks** — if hooks fail, fix the underlying issue, do not bypass.
8. **Print the post-commit summary** showing the resulting log.
9. **Apply config overrides** from `commit-config.json` if present.
10. **Detect task references** from branch name when `auto_refs: true` and add `Refs: #N` to the commit body.

### Ask First (requires explicit user confirmation)

1. **Amending an existing commit** — `git commit --amend` or interactive rebase.
2. **Splitting a commit** that has already been made.
3. **Reordering commit groups** when the user has not specified the order.
4. **Including files the user explicitly excluded** earlier in the conversation.
5. **Committing files that look like secrets** (`.env`, `*.pem`, `id_rsa`, anything matching credential patterns) — refuse and ask.
6. **Committing large binary files** (>1 MB) without explicit confirmation.
7. **Force-staging a hunk** the user did not mention.
8. **Modifying scope aliases** beyond what `commit-config.json` defines.

### Never Do (absolute, no override)

1. **Never auto-commit** after completing any task. Wait for explicit request.
2. **Never run `git push`** — the workflow ends at the local commit.
3. **Never use `--no-verify`** or bypass pre-commit/commit-msg hooks.
4. **Never amend a commit** without explicit user request.
5. **Never use `git rebase -i`** without explicit user request.
6. **Never use `git reset --hard`** to discard uncommitted work.
7. **Never use `git add .` or `git add -A`** — always stage specific files.
8. **Never commit secrets or credential files** — refuse and report.
9. **Never edit commit messages** of already-pushed commits.
10. **Never use `git filter-branch`, `git filter-repo`, or BFG** without explicit user request.
11. **Never include real PII** in commit messages.
12. **Never sign commits** unless `commit-config.json` says so.

### Violation protocol

If you (the agent) realize you have violated or are about to violate any rule above:

1. **Stop.** Do not run any further git commands.
2. **Surface the violation.** Tell the user explicitly: which rule, which commit (SHA), what was done.
3. **Propose a correction** — `git reset --soft HEAD~1` to undo a commit, restore staged files, etc.
4. **Wait for user confirmation** before applying the correction.
5. **Do not paper over** git mistakes. The reflog remembers; transparency is required.

## Configuration

Reads `commit-config.json` from the project root (optional). See `commit-config.example.json` in this skill directory for the schema.

Defaults if config does not exist:

- `additional_heuristics`: `{}` (no extra path→type mappings)
- `commit_order_override`: `null` (use default order from workflow)
- `auto_refs`: `true` (auto-detect task references from branch name)
- `scope_aliases`: `{}` (no scope renaming)

When a config file is present, merge its values with the defaults. Config values take precedence.

## Pre-Commit Checks

Before executing, verify all of the following:

1. **Inside a git repo**: `git rev-parse --is-inside-work-tree` must succeed
2. **No rebase in progress**: `git rev-parse -q --verify REBASE_HEAD` must fail
3. **No merge in progress**: `git rev-parse -q --verify MERGE_HEAD` must fail
4. **Changes exist**: `git status --porcelain` must produce output

If any check fails, report the issue to the user and stop.

## Execution

Load and execute the workflow defined in `references/commit-workflow.md` (relative to this skill directory).

The workflow handles: unstaging, file grouping by path heuristics, Conventional Commit message composition, staged commits in topic order, and task reference extraction.

If `commit-config.json` is present, apply its overrides:

- **additional_heuristics**: merge with built-in path→type mappings (config takes precedence on conflicts)
- **commit_order_override**: replace the default group ordering
- **scope_aliases**: rename scopes in commit headers (e.g., `{"backend": "api"}` → `feat(api)` instead of `feat(backend)`)
- **auto_refs**: if `false`, skip automatic task reference extraction from branch name

## Integration

After committing, **optionally suggest** (do not execute automatically):

- _"Vuoi aggiornare lo stato delle issue collegate tramite `pm-github-workflow`?"_

Only suggest if task references were detected in the commits.

## Post-Commit Summary

After all commits are created, print a summary:

```
git --no-pager log -n 10 --pretty=format:"%h %ad %s" --date=short
```

**Do NOT execute `git push` after the summary.** The workflow ends here.

## Verification

Before considering the commit task complete, the agent must produce **evidence** that each item below holds.

### Mandatory checks (every task)

- [ ] User explicitly requested a commit (or `/commit-files`).
- [ ] Pre-commit checks all passed (in repo, no rebase/merge, changes exist).
- [ ] Each commit message follows Conventional Commits format.
- [ ] Each commit groups files by topic; no kitchen-sink commit.
- [ ] Files were staged explicitly by name, never `git add .` or `-A`.
- [ ] Pre-commit hooks ran and passed (or were fixed and re-run, never bypassed).
- [ ] Post-commit summary printed (`git log -n 10`).
- [ ] No `git push` executed.

### Conditional checks

If `commit-config.json` exists:
- [ ] Config loaded and overrides applied.

If `auto_refs: true` and a branch name suggests an issue:
- [ ] `Refs: #N` added to relevant commit bodies.

If task references were detected:
- [ ] Suggestion to update issue status via `pm-github-workflow` shown to user (suggestion only, not invocation).

### Disqualifying signals (block "done")

- A commit made without explicit user request
- A `git push` executed
- A `--no-verify` flag used
- A `git add .` or `git add -A` used
- A commit that bundles unrelated changes
- A commit message that does not follow Conventional Commits
- A commit containing files that look like secrets (`.env`, keys, credentials)
- A pre-commit hook failure that was bypassed instead of fixed
- A commit amended without explicit user request
- Real PII in a commit message

## Self-Review

The self-review lens for this skill — Common Rationalizations, Red Flags, and Ask First decision aids — lives in `references/self-review.md`. Load it before declaring done.


## Bundled Resources

```
commit-manager/
├── SKILL.md
├── commit-config.example.json
└── references/
    ├── commit-workflow.md
    └── self-review.md         # loaded before declaring done
```
