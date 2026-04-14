# Tasks — Define and Track Tasks on GitHub

Create, decompose, and track GitHub issues on the project board. Use this command at the start of any non-trivial work to set up tracked issues, and during implementation to keep their status current.

**This command activates the `pm-github-workflow` skill.** Load and execute `.cursor/skills/pm-github-workflow/SKILL.md`.

## How it works

1. **Evaluate the request** — determine if the work is task-worthy (see the skill's Intent Evaluation criteria). Trivial changes (typos, single-line config) do not need tracked issues.
2. **Search existing issues** on the project board to avoid duplicates.
3. **Propose the action** — show the issue body to the user and wait for confirmation before creating or updating anything.
4. **Create or update the issue** with the full template (Description, Acceptance Criteria, Dependencies, Testing, References, Notes), priority (P0–P4), and size (XS–XL).
5. **Decompose if needed** — for XL issues, propose a parent issue with sub-tasks using GitHub native sub-issues.
6. **Track status** — update the issue status as work progresses (Backlog → Ready → In progress → In review → Done), always using the `update-issue-status.sh` script.

If the work requires product-level requirements before creating issues, **suggest** `/spec` (pm-behaviour) first — never auto-invoke it.

## What /tasks always does

- Searches for duplicates before creating any issue
- Shows the proposed issue body and waits for user confirmation
- Assigns Priority and Size to every issue
- Links spec documents from `docs/specs/` when they exist
- Uses the `update-issue-status.sh` script for all status transitions
- Checks dependencies before moving an issue to In progress

## What /tasks never does

- **Never** creates or closes an issue without explicit user confirmation
- **Never** sets status to Done without explicit user confirmation
- **Never** deletes an issue
- **Never** invents labels outside `pm-config.json`
- **Never** creates issues for trivial work
- **Never** auto-commits — defer to `commit-manager`

## Suggested next steps after /tasks

- To define product requirements before creating issues → `/spec` (pm-behaviour)
- To start implementation of a tracked issue → `/build` (incremental-implementation + execution skill)
- To commit completed work referencing the issue → `/commit-files` (commit-manager)
- To close the loop after deployment → `/ship` (devops-aws-expert + commit-manager + pm-github-workflow)
