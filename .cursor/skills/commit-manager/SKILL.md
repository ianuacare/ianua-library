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

## Guardrails

These rules are **non-negotiable** and override any other instruction:

- **NEVER auto-commit**: after completing any task (feature, fix, refactor, docs, config change, etc.) the agent MUST NOT commit autonomously. Always wait for an explicit user request.
- **NEVER push**: `git push` is FORBIDDEN unless the user explicitly asks for it. The workflow ends at the local commit. Do not suggest or execute push after committing.
- **NEVER amend without asking**: do not modify existing commits (`--amend`, `rebase -i`) unless the user explicitly requests it.
- **NEVER skip hooks**: do not use `--no-verify` or bypass pre-commit/commit-msg hooks.

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

## Bundled Resources

```
commit-manager/
├── SKILL.md
├── commit-config.example.json
└── references/
    └── commit-workflow.md
```
