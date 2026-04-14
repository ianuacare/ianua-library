# Review — Five-Axis Code Review

Review the current diff (or a specified set of files) across five axes: correctness, readability, architecture, security, performance. The right execution skill is selected per file based on the technology.

## How it works

1. **Identify the changed files.** Default to `git diff` against the upstream branch. If the user specifies files, use those.
2. **Group files by domain** and load the matching execution skill in **review mode**:
   - `*.ts`, `*.tsx` (backend) → `backend-ts-expert`
   - `*.py` (backend) → `backend-py-expert`
   - `*.ts`, `*.tsx`, `*.vue`, `*.svelte` (frontend) → `frontend-ts-expert`
   - `*.tf`, `cdk.*`, `Dockerfile`, `.github/workflows/*` → `devops-aws-expert`
3. **For each loaded skill**, walk its `Operating Boundaries`, `Verification`, and `references/self-review.md` against the diff. Flag every match in the Red Flags lists as a finding.
4. **Synthesize findings** into a single report with severity prefixes:
   - **Critical:** must be fixed before merge (blocks "done")
   - **Important:** should be fixed in this PR
   - **Suggestion:** consider for follow-up
   - **Nit:** style/preference
5. **For SEO-affecting changes** (meta tags, canonicals, structured data, robots.txt) → also load `seo-expert`
6. **For UX-affecting changes** (component layouts, accessibility) → cross-check against existing `WF-NNN` and `UXD-NNN`

## Output format

```
## Review Summary

**Files reviewed:** N
**Skills loaded:** [list]

### Critical (N)
- [file:line] Description — rule violated

### Important (N)
- [file:line] Description

### Suggestions (N)
- [file:line] Description

### Nits (N)
- [file:line] Description

### Verification status
- [ ] Mandatory checks from each loaded skill
- [ ] Disqualifying signals: none / list
```

## What review mode does NOT do

- It does **not** modify code. Findings are reported, the user decides.
- It does **not** auto-create issues. Suggest `pm-github-workflow` for follow-up tracking.
- It does **not** auto-commit. The fix workflow goes through `/build` → `/commit-files`.
