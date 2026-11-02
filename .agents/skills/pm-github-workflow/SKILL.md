---
name: pm-github-workflow
description: >-
  Manages GitHub issue lifecycle and project board status transitions.
  Use this skill when the user asks to create, update, or close GitHub
  issues, manage tasks on the project board, track progress status,
  assign priority (P0-P2) or size (XS-XL) to issues, manage
  dependencies between tasks, move issues between statuses (backlog,
  ready, in-progress, in-review, done), create epics with sub-tasks,
  or reference issues in commits. Do NOT use for product decisions or
  PRDs (→ pm-behaviour).
---

# GitHub Workflow — Project Management

## Target project

- **Board:** [easydoctor-io / Project 5](https://github.com/orgs/easydoctor-io/projects/5)
- **Org:** `easydoctor-io`
- **Default repo for issues:** `easydoctor-io/easydoctor-rails`

## Configuration

This skill reads project-specific values from `pm-config.json` in this directory (`/.claude/skills/pm-github-workflow/pm-config.json`). The file is checked in for this repository and already maps **Status** options for project 5.

**If the board columns change**, refresh field IDs:

```bash
gh project field-list 5 --owner easydoctor-io --format json
```

Copy `pm-config.example.json` → `pm-config.json` only when bootstrapping a new clone; do not edit the example as the live source of truth.

## Operating Boundaries

This skill operates under three explicit boundary tiers. Issue lifecycle management touches shared state (the GitHub project board) so the rules are strict.

### Always Do (no exceptions)

1. **Search before creating** — every "create issue" intent first runs the project search to avoid duplicates.
2. **Wait for user confirmation** before creating, closing, or transitioning to Done.
3. **Issue body uses the registered template** — Description, Acceptance Criteria, Dependencies, Testing, References, Notes. No free-form issues.
4. **Every issue gets a Priority (P0–P2) and Size (XS–XL)** — defaults P2/M when unclear, then ask. (Project 5’s Priority column is P0/P1/P2 only.)
5. **Acceptance Criteria are verifiable** — checkboxes the human can tick, not "works well".
6. **Link the spec** — if a `docs/specs/` artifact exists for the feature, link it. Mandatory.
7. **Use `Refs: #N` / `Closes #N`** in commit messages, not free text.
8. **Check dependencies before "In progress"** — if blocked, notify the user instead of starting work.
9. **Use only labels defined in `pm-config.json`** — never invent new labels on the fly.
10. **Use the `update-issue-status.sh` script** for transitions, not raw `gh` commands.
11. **Use GitHub native sub-issues** for parent/child, not custom fields.

### Ask First (requires explicit user confirmation)

1. **Creating a new issue** — propose it first, show the body, confirm.
2. **Closing an issue** — always.
3. **Transitioning In review → Done** — always, no exceptions.
4. **Reopening a closed issue.**
5. **Modifying labels on an existing issue.**
6. **Modifying Priority or Size on an existing issue.**
7. **Adding or removing a sub-issue relationship.**
8. **Splitting an XL issue into sub-tasks** — propose decomposition, ask before creating sub-issues.
9. **Editing acceptance criteria** after the issue is in In progress — confirm scope creep.
10. **Adding a new label to `pm-config.json`** — labels are project-wide.

### Never Do (absolute, no override)

1. **Never close an issue without explicit user confirmation.**
2. **Never delete an issue.**
3. **Never modify `pm-config.json` field IDs or option IDs** without explicit user request.
4. **Never create issues for trivial work** (typos, single-line config changes).
5. **Never set status to Done** before the user confirms the merge or release.
6. **Never invent labels** outside `pm-config.json`.
7. **Never skip the search step** before creating an issue.
8. **Never bypass the `update-issue-status.sh` script** for status transitions.
9. **Never use the `--force` flag** on any `gh` command without explicit user request.
10. **Never auto-commit** — defer to `commit-manager`.
11. **Never include real PII** in issue bodies or references.

### Violation protocol

If you (the agent) realize you have violated or are about to violate any rule above:

1. **Stop.** Do not run any further `gh` commands.
2. **Surface the violation.** Tell the user explicitly: which rule, which issue, what was done.
3. **Propose a correction** — reopen the issue, revert the status, restore the label.
4. **Wait for user confirmation** before applying.
5. **Do not paper over.** The project board is shared state; transparency is required.

## Intent Evaluation (When to Activate)

The agent MUST evaluate every user request against these criteria before starting implementation:

### Task-worthy (activate tracking)

- New feature or capability
- Non-trivial bug fix (multi-file, requires investigation)
- Refactoring that touches multiple files or changes architecture
- Anything the user explicitly calls a task, issue, story, or ticket
- Work estimated at size S or larger

### Trivial (skip tracking)

- Typo fix, single-line config change
- Code exploration or reading
- Documentation-only edits (unless part of a larger story)
- One-liner fixes with obvious scope

### Uncertain

Ask the user directly: _"This looks like it could warrant a tracked issue. Should I create one?"_

## Agent Workflow (Lifecycle)

When a request is task-worthy, follow this sequence:

1. **Receive request** → evaluate if task-worthy (see above)
2. **Search existing issues** on the project board:
   ```bash
   gh project item-list 5 --owner easydoctor-io --limit 200 --format json
   ```
3. **Propose action** — link to existing issue or create new one → **wait for user confirmation**
4. **Create/update issue** with full spec (see Issue Body Template below), including priority, size, dependencies → set status to **"In progress"**
5. **Implement**, referencing the issue in commits (`Refs: #N`)
6. **Verify acceptance criteria** → check them off in the issue body → set status to **"In review"**
7. **"Done"** → ONLY on explicit user confirmation

## Status Model

```
Backlog ──→ Ready ──→ In progress ──→ In review ──→ Done
                          ↑                │
                          └── (rework) ────┘
```

## Transition Rules

| From | To | Trigger | Who |
|------|----|---------|-----|
| Backlog | Ready | Requirements clear, spec complete, acceptance criteria present | User or planning |
| Ready | In progress | Agent starts implementation | Agent (automatic) |
| In progress | In review | Commit done, tests pass, all acceptance criteria met | Agent (automatic) |
| In review | Done | Review approved and merged | **Only on explicit user confirmation** |
| In review | In progress | Changes requested during review | Agent or user |
| In progress | Ready | Work suspended or reprioritized | User |

### Operational Rules

1. **Ready → In progress**: update status BEFORE writing code.
2. **In progress → In review**: update status AFTER commit, after verifying tests pass and all acceptance criteria are satisfied.
3. **In review → Done**: NEVER without explicit user confirmation.
4. Work on the current branch — do not create branches for individual issues.

## Priority, Size, and Dependencies

### Priority (P0–P2)

The agent MUST assign a priority to every issue created. The project board single-select only includes **P0, P1, P2**.

| Priority | Meaning | Guideline |
|----------|---------|-----------|
| P0 | Critical/blocker | Production down, data loss, security vulnerability |
| P1 | High urgency | Blocks other work, impacts users significantly |
| P2 | Normal | Default — standard feature or bug fix |

If priority is unclear, propose **P2** and ask for confirmation.
Priority influences work order: P0/P1 issues take precedence.

### Size (XS–XL)

The agent MUST estimate sizing for every issue created.

| Size | Effort | Guideline |
|------|--------|-----------|
| XS | < 1 hour | Trivial change, single file |
| S | Half day | Small feature, few files |
| M | 1 day | Standard feature |
| L | 2–3 days | Complex feature, multiple components |
| XL | 1 week+ | Epic-scale — should be decomposed into sub-tasks |

The agent MUST propose decomposition into sub-tasks for issues sized XL.

### Dependencies

Track dependencies between issues using a `## Dependencies` section in the issue body.

Format:
- `- Blocked by #N: [reason]`
- `- Blocks #N: [reason]`

Rules:
- The agent MUST check dependencies before setting an issue to "In progress" — if blocked, notify the user.
- When a blocking issue is completed, the agent proposes unblocking dependent issues.

### Parent/Children Relationships

Use **GitHub Sub-issues** (native feature) to track parent/children relationships.

**Mechanism**: GitHub provides a built-in "Sub-issues" field on issues. When you add sub-issues to a parent, GitHub automatically tracks progress and shows a completion bar on the parent issue. This is managed via the issue UI or the `gh` CLI — no custom project fields required.

**CLI commands**:

```bash
# Add a sub-issue to a parent
gh issue edit <parent-number> --add-sub-issue <child-number> -R easydoctor-io/easydoctor-rails

# Remove a sub-issue from a parent
gh issue edit <parent-number> --remove-sub-issue <child-number> -R easydoctor-io/easydoctor-rails

# List sub-issues of a parent (via API)
gh issue view <parent-number> -R easydoctor-io/easydoctor-rails --json subIssues
```

Additionally, include a `[tasklist]` block in the parent issue body for human-readable tracking:

````markdown
```[tasklist]
### Sub-tasks
- [ ] #101
- [ ] #102
```
````

When the agent creates an issue that is part of a larger effort:
1. Check if a parent issue (epic/story) exists
2. If yes, add the new issue as a sub-issue (`gh issue edit <parent> --add-sub-issue <new>`) and update the parent's tasklist block
3. If the work is large enough to require decomposition, propose creating a parent issue with sub-issues

When a sub-issue is completed, GitHub automatically updates the parent's progress tracker.

## Issue Body Template

```markdown
## Description
[What and why]

## Acceptance Criteria
- [ ] Verifiable criterion 1
- [ ] Verifiable criterion 2

## Dependencies
- Blocked by #N: [reason]
- Blocks #N: [reason]
(or "None" if no dependencies)

## Testing
- **How to test**: [Step-by-step instructions]
- **Environment/credentials**: [Required setup or "N/A"]
- **Expected behavior**: [What the tester should observe]

## References
- Spec: [link to spec document, e.g. `docs/specs/feature-x.md`]
- Docs: [link to relevant documentation, PRD, design doc, Figma, etc.]
- Related: #N, #M [related but non-blocking issues]

## Notes
[Context, constraints]
```

### Rules for References

- The agent MUST search for and link relevant spec documents (`docs/specs/`, PRD, design docs) when creating an issue
- If a spec exists for the feature, the link is mandatory
- Link external documentation (Figma, Notion, Google Docs) if mentioned by the user
- Link related issues (not dependencies, but useful context) in the References section

### Parent Issue Template (Epic/Story)

````markdown
## Description
[Overall objective]

## Sub-tasks
```[tasklist]
### Tasks
- [ ] #N: [brief description]
- [ ] #M: [brief description]
```

## Acceptance Criteria
- [ ] All sub-tasks completed
- [ ] [Integration/end-to-end criteria]

## Notes
[Context, constraints, timeline]
````

## Updating Issue Status

Run the helper script in `scripts/`:

```bash
bash .claude/skills/pm-github-workflow/scripts/update-issue-status.sh <issue-number> <status>
```

Valid statuses: `backlog`, `ready`, `in-progress`, `in-review`, `done`.

Example:

```bash
bash .claude/skills/pm-github-workflow/scripts/update-issue-status.sh 42 in-progress
```

The script reads all values from `pm-config.json`. Dependencies: `gh` CLI (authenticated) + `python3` (stdlib only).

## Commit References

- Extract issue number from context (user message, plan, or referenced issue).
- Use `Refs: #<number>` to reference the issue in commit body.
- Use `Closes #<number>` when the commit completes the issue's work.
- Multiple issues: `Refs: #12, #15`.

## Labels

Valid labels are defined in `pm-config.json` under the `labels` key. Use only labels from the config to keep the project consistent.

## Verification

Before considering an issue management task complete, the agent must produce **evidence** that each item below holds.

### Mandatory checks (every task)

If the task **created an issue**:
- [ ] User confirmed the proposed issue body before creation.
- [ ] Search for duplicates was performed and shown to the user.
- [ ] Issue body matches the registered template (Description, AC, Dependencies, Testing, References, Notes).
- [ ] Priority and Size assigned (defaults P2/M with note if unclear).
- [ ] Spec link present if `docs/specs/` artifact exists.
- [ ] Labels are all from `pm-config.json`.
- [ ] Status set to the appropriate starting column (usually Backlog or Ready).
- [ ] Issue URL shown to the user.

If the task **transitioned an issue**:
- [ ] Transition followed the Status Model arrow (no skipping).
- [ ] Used `update-issue-status.sh`, not raw `gh project item-edit`.
- [ ] Dependencies checked before moving to In progress.
- [ ] If In review → Done, user confirmation obtained in writing.
- [ ] New status visible on the board (verified via `gh project item-list`).

If the task **referenced issues in commits**:
- [ ] Used `Refs: #N` or `Closes #N` syntax.
- [ ] Issue numbers verified to exist before referencing.

If the task **created sub-issues**:
- [ ] Parent issue's `[tasklist]` block updated.
- [ ] Sub-issue relationship created via `gh issue edit --add-sub-issue`, not custom fields.

### Disqualifying signals (block "done")

- An issue created without prior search
- An issue closed without explicit user confirmation
- A status transition to Done without user confirmation
- An issue body missing Acceptance Criteria
- A label not in `pm-config.json`
- A `gh` command run with `--force` without explicit user request
- A status transition that skips a column in the Status Model
- An issue created for trivial work
- Real PII in an issue body

## Self-Review

The self-review lens for this skill — Common Rationalizations, Red Flags, and Ask First decision aids — lives in `references/self-review.md`. Load it before declaring done.

## Gotchas

- `gh project item-list` defaults to `--limit 50` — use `--limit 200` for large backlogs.
- The `update-issue-status.sh` script requires `gh` CLI authenticated with org access.
- All project-specific values live in `pm-config.json` — if the project board columns or Status options change, update the config, not the script.
- An issue in Backlog without acceptance criteria is NOT ready — do not move it to Ready until criteria are added.
- When checking off acceptance criteria, use `gh issue edit` to update the body, not comments.
- **Always check dependencies** before starting work on an issue — if it's blocked, notify the user first.
