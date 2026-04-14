# Commit Manager — Self-Review Lens

Loaded on demand before declaring done.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The task is done, the user obviously wants me to commit." | "Obviously" is the agent's interpretation. Wait for explicit request. |
| "It's faster to bundle everything into one commit." | One giant commit is impossible to review, debug, or revert. Always split by topic. |
| "I'll use `git add .`, the user wants everything committed." | `git add .` includes files the user did not see (temp files, secrets, generated artifacts). Stage explicitly. |
| "The pre-commit hook is failing on a lint warning, I'll bypass it." | The hook exists for a reason. Fix the warning. `--no-verify` is forbidden. |
| "I'll amend the previous commit to fix the typo." | Amending rewrites history. The user must request it explicitly. |
| "The commit message is descriptive enough without a scope." | Conventional Commits with scope is the project standard. Use it. |
| "The user said 'commit and push'." | Push is forbidden unless the user separately requests it after the commit. |
| "I'll commit the `.env` file, the user obviously needs it for testing." | `.env` is a secret file. Refuse and report. |
| "I'll squash these into one commit, it's cleaner." | Squashing destroys topic separation. Each commit should be revertable on its own. |
| "I'll skip the post-commit summary, the user can see the log." | The summary is the audit trail. Always print it. |
| "I'll commit the binary file the user generated, it's only 5 MB." | Binary files bloat the repo permanently. Ask first. |
| "The user just said 'commit', I can decide the order." | The default order from the workflow is the registered standard. Use it unless the user overrides. |

---

## Red Flags

### In the staging area

- A `.env`, `*.pem`, `id_rsa`, or any credential-looking file staged
- A binary file >1 MB staged without explicit confirmation
- A generated file (`dist/`, `build/`, `node_modules/`) staged
- A `.DS_Store`, `Thumbs.db`, or IDE config staged
- Files outside the user's stated scope staged
- Many unrelated files in a single commit

### In commit messages

- Subject line not in Conventional Commits format
- Subject line >72 characters
- Body containing real user PII (emails, names, phone numbers)
- Body containing secrets, API keys, or tokens
- A "Refs: #N" pointing to a non-existent issue
- A "Closes #N" without user confirmation that the issue is actually done

### In the agent's behavior

- The agent commits without explicit user request
- The agent runs `git push`
- The agent uses `--no-verify`
- The agent uses `git add .` or `git add -A`
- The agent amends without asking
- The agent rebases interactively without asking
- The agent bundles unrelated changes
- The agent skips the post-commit summary
- The agent reports "committed" without showing the commit SHAs
- The agent uses `git filter-branch` or similar history rewriting tools

### In the result

- A commit message that does not match the staged changes
- A commit that mixes feature and fix
- A commit that mixes code and unrelated formatting
- A commit ahead of a hook failure that was bypassed

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Committing files the user explicitly named | **No** | Direct request |
| Committing files that look like secrets | **Yes (always — refuse first)** | Credential leak risk |
| Committing a binary file <1 MB | **No** | Routine |
| Committing a binary file >1 MB | **Yes** | Repo bloat |
| Splitting into multiple commits by topic | **No** | "Always Do" |
| Splitting one commit into more after it was made | **Yes** | History rewrite |
| Reordering commits within the workflow defaults | **No** | Standard |
| Reordering commits via interactive rebase | **Yes** | History rewrite |
| Amending the most recent commit | **Yes** | History rewrite |
| Amending an earlier commit | **Yes (with extra confirmation)** | More dangerous |
| Adding a `Refs: #N` from branch name when `auto_refs: true` | **No** | Standard |
| Adding a `Closes #N` | **Yes** | Auto-closes the issue on push |
| Bypassing a failing hook | **Yes (and refuse — fix the issue)** | Hooks exist for a reason |
| Running `git push` | **Yes (always)** | Out of scope by default |
| Running `git stash` to set aside changes | **Yes** | State change |
| Running `git reset --soft HEAD~1` to undo a commit | **Yes** | History change |
| Running `git reset --hard` | **Yes (and warn loudly)** | Discards work |
| Suggesting `pm-github-workflow` after a commit with task refs | **No** | Suggestion is fine |

### Default rule

The git history is shared state. Every history-rewriting operation requires user confirmation. **Never auto-commit. Never push. Never bypass hooks. Never `git add .`.**
