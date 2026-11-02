---
name: github-issue-workflow
description: >-
  Manage GitHub issues for task tracking, feature roadmap, and spec-to-code traceability.
  Use when creating issues from specs, updating issue status, linking PRs to issues,
  managing milestones, or tracking development progress on GitHub.
---

# GitHub Issue Workflow

Manages the full lifecycle of GitHub issues from spec decomposition to PR merge.

## Creating Issues from Specs

Use `gh` CLI to create issues with the standard template:

```bash
gh issue create \
  --title "[feat] Short description of the task" \
  --label "feature,pathways" \
  --milestone "Sprint 1" \
  --body "$(cat .cursor/skills/github-issue-workflow/issue-template.md)"
```

Edit `issue-template.md` before each creation, or pass the body inline.

## Issue Title Conventions

Format: `[<type>] <description>`

| Type | When |
|------|------|
| `[feat]` | New functionality |
| `[fix]` | Bug fix |
| `[refactor]` | Code quality improvement |
| `[test]` | Test-only change |
| `[docs]` | Documentation |
| `[chore]` | Infrastructure, dependencies |

Examples:
- `[feat] Add step reordering via drag-and-drop`
- `[fix] Prevent duplicate survey submission on refresh`
- `[test] Add request specs for vitals API endpoint`

## Labels

### Type Labels (apply exactly one)
`feature`, `bug`, `refactor`, `test`, `docs`, `chore`, `security`, `performance`

### Domain Labels (apply one or more)
`pathways`, `surveys`, `patients`, `api`, `auth`, `admin`, `jobs`, `ui`, `infra`

### Status Labels (managed during development)
`in-progress`, `blocked`, `needs-review`, `on-hold`

## Branch → Issue Linking

```bash
# Create branch referencing issue
git checkout -b feat/42-step-reordering

# PR body must close the issue
gh pr create \
  --title "feat(pathways): add step reordering via drag-and-drop" \
  --body "Closes #42"
```

GitHub auto-closes the issue when PR merges to main.

## Tracking & Status Management

```bash
# List open issues by milestone
gh issue list --milestone "Sprint 1"

# List issues by label
gh issue list --label "feature,pathways"

# Mark as in-progress
gh issue edit 42 --add-label "in-progress"

# Add comment with progress update
gh issue comment 42 --body "Migration done, working on model specs"

# Close manually (if not via PR)
gh issue close 42 --comment "Completed in #78"
```

## Milestones

Map milestones to sprints or version releases:

```bash
# Create a milestone
gh api repos/:owner/:repo/milestones \
  --method POST \
  --field title="Sprint 1" \
  --field due_on="2025-04-30T23:59:59Z"

# List milestones
gh api repos/:owner/:repo/milestones
```

## Issue Template Reference

See [issue-template.md](issue-template.md) for the standard issue body format.
