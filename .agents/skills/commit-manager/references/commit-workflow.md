# Commit Workflow — Split changes into meaningful commits

Create a focused series of commits from your current working tree using Conventional Commits. This command analyzes changed files, groups them by topic, and commits each group with a clear, scannable message.

Behavior (non-interactive):
- Unstages everything first (safe): `git reset`
- Detects changed files and groups by topic using path heuristics
- Composes Conventional Commit headers and concise bodies
- Stages files per group and commits in a sensible order
- Prints a short summary of the created commits

Guardrails:
- Aborts if not inside a git repo or if a rebase/merge is in progress
- Skips if there are no changes
- Does not split hunks within a single file (file-level grouping only)
- If some files contain mixed-topic changes, they will be committed together in the most likely group

Heuristics (path → type(scope)):
- `specs/api/openapi.yaml`, `README-API.md`, `docs/api.html`, `dist/api-spec.yaml` → `docs(api)`
- `specs/tech/**` → `docs(tech)`
- `specs/product/**` → `docs(product)`
- `specs/business/**` → `docs(business)`
- Backend code: `src/**`, `server/**`, `backend/**` → `feat|fix|refactor(backend)`
- Frontend code: `app/**`, `web/**`, `client/**`, `frontend/**` → `feat|fix|refactor(frontend)`
- Tests: `tests/**`, `__tests__/**` → `test`
- Build/CI: `Dockerfile*`, `docker-compose*`, `.github/**`, `.circleci/**`, `.gitlab/**` → `build|ci`
- Config/Tooling: `.cursor/**`, `.vscode/**`, `.editorconfig`, `.gitignore` → `chore(config)`
- Dependencies: `package*.json`, `pnpm-lock.yaml`, `yarn.lock` → `chore(deps)`
- Everything else → `chore(misc)`

Type selection for backend/frontend groups (deterministic defaults):
- Prefer `feat(scope)` if the group contains new files that export symbols, new routes/controllers, or new UI components/pages (creation-dominant change)
- Prefer `fix(scope)` if filenames, branch name, or diff snippets indicate bug fixes (e.g., contains "fix", "hotfix", "bug", or failing test adjustments)
- Otherwise default to `refactor(scope)` for code-only reshaping without new behavior

Conventional Commit rules:
- Header: `<type>(<scope>): <summary ≤ 72 chars>`
- Body: short bullets with notable changes; include file counts where helpful
- Types: `feat, fix, docs, style, refactor, perf, test, build, ci, chore`
- Append a `Refs: [ID]` line at end of body when a task/story/epic ID is detected (e.g., from branch name or commit context).

Task references in commit messages (auto-detected):
- Extract issue number from branch name: `git rev-parse --abbrev-ref HEAD` and match the pattern `<type>/<number>-<slug>` (e.g., `feat/12-morse-score` → `#12`)
- Also match legacy patterns: `(task|story|epic)-\d+`
- Extract issue references from commit context or referenced tasks in the current work session
- Combine, deduplicate, and append as `Refs: #123` at the end of the commit body (use GitHub `#` syntax)
- If the commit completes the work for the issue, use `Closes #123` instead of `Refs: #123`
- If none found, omit the line

Execution steps (perform automatically, no extra confirmations):
1) Verify repo status is safe to operate:
   - `git rev-parse --is-inside-work-tree`
   - `git rev-parse -q --verify MERGE_HEAD` (abort if present)
   - `git rev-parse -q --verify REBASE_HEAD` (abort if present)
2) Unstage everything: `git reset`
3) Gather changed files: `git status --porcelain`
4) Build topic groups using the heuristics above
5) For each group in this order: deps → build/ci → config → api docs → backend → frontend → tests → product/tech/business docs → misc
   - Stage exactly those paths: `git add -A -- <paths...>`
   - Create commit with a clear header and a concise body listing highlights and representative files
   - If task/story/epic IDs were detected, append `Refs: <ids>` as the last line of the body
6) Print a summary: `git --no-pager log -n 10 --pretty=format:"%h %ad %s" --date=short`

Notes:
- Avoid interactive commands (`git add -p`) to keep this non-interactive
- If no files match a group, skip that group gracefully
- If `specs/api/openapi.yaml` is included, prefer `docs(api): update OpenAPI spec` as the header
