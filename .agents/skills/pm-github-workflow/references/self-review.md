# PM GitHub Workflow — Self-Review Lens

Loaded on demand before declaring done.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll just create the issue, the user can edit it after." | Creating an issue is shared state. Once created, every team member sees it. Confirm first. |
| "The search returned no exact match, I'll create a new issue." | "No exact match" ≠ "no related issue". Show the user the closest matches before creating. |
| "I'll close this stale issue, it's clearly abandoned." | "Clearly abandoned" is your interpretation. Always confirm. |
| "The user said 'mark it done', so I'll move it to Done." | "Mark it done" is ambiguous — review or merged? Confirm which. |
| "I'll skip the spec link, the issue title is descriptive." | Issue titles drift. The spec link is the durable reference. |
| "I'll use a new label, it's more descriptive." | New labels fragment the project. Use only labels in `pm-config.json` or propose adding one. |
| "Priority is unclear, I'll skip the field." | Skipping the field breaks board sorting. Default P2 and ask. |
| "The dependency is loose, I won't add it to the body." | Loose dependencies become surprise blockers. Document them. |
| "I'll edit the acceptance criteria, scope changed slightly." | Scope changes are decisions. Confirm with the user, then edit. |
| "I'll skip the sub-issue tracking, the parent body is enough." | GitHub's native sub-issues give automatic progress tracking. Use them. |
| "The script doesn't work, I'll just run `gh project item-edit` directly." | The script encodes the field/option mapping. Bypassing it leads to wrong status values. Fix the script. |
| "I'll force-push the issue body to fix a typo." | `gh issue edit` is fine for typos; never use `--force` flags. |

---

## Red Flags

### In issue creation

- An issue created without a prior search
- An issue without Acceptance Criteria
- An issue without Priority or Size
- An issue with a label not in `pm-config.json`
- An issue body missing the spec link when a spec exists
- An issue with vague or unverifiable AC
- An issue created for a typo or one-line config change
- Real user PII in the issue body
- An issue with no References section

### In status transitions

- A transition that skips a column in the Status Model
- A transition to Done without user confirmation
- A transition to In progress while the issue is blocked
- An issue moved back to Ready without a reason
- A status update done with raw `gh project item-edit` instead of the script

### In sub-issue management

- A parent issue without a `[tasklist]` block
- A sub-issue relationship not reflected in the parent body
- An XL issue not decomposed into sub-tasks

### In the agent's behavior

- The agent creates an issue without confirming
- The agent closes an issue without confirming
- The agent invents labels
- The agent skips the search step
- The agent uses raw `gh` commands instead of the helper script
- The agent reports "issue created" without showing the URL
- The agent runs commands with `--force` without explicit request

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Searching the project for existing issues | **No** | Required step |
| Creating an issue | **Yes** | Shared state |
| Updating an issue body to add a missing reference | **No** | Improves accuracy |
| Updating acceptance criteria after the issue is In progress | **Yes** | Scope change |
| Transitioning Backlog → Ready | **No (with checks)** | Routine, but require AC present |
| Transitioning Ready → In progress | **No** | Standard workflow |
| Transitioning In progress → In review | **No** | After commit + tests pass |
| Transitioning In review → Done | **Yes (always)** | Final state, confirm merge |
| Reopening a closed issue | **Yes** | State change |
| Closing an issue | **Yes** | Always |
| Adding a label from `pm-config.json` | **No** | Standard |
| Adding a label not in `pm-config.json` | **Yes** | Project-wide convention |
| Modifying Priority or Size on an existing issue | **Yes** | Reprioritization |
| Setting Priority or Size on a new issue | **No** | Required field |
| Splitting an XL issue | **Yes** | Decomposition decision |
| Adding a sub-issue to an existing parent | **Yes** | Relationship change |
| Creating sub-issues for a brand-new epic | **Yes** | Confirm decomposition |
| Referencing the issue in a commit (`Refs: #N`) | **No** | Standard |
| Closing the issue via `Closes #N` in a commit | **Yes** | Auto-close = state change |
| Editing `pm-config.json` field IDs | **Yes (always)** | Configuration drift risk |

### Default rule

The project board is shared state. Every state-changing operation requires user confirmation. **Search before create. Confirm before close. Never invent labels.**
