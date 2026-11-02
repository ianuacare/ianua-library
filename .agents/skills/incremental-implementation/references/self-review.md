# Incremental Implementation — Self-Review Lens

Loaded on demand after every slice and at task completion.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's faster to do it all at once and commit at the end." | It feels faster until something breaks, and you cannot find which 500 lines caused it. The increment cycle is faster overall because every checkpoint is a save point. |
| "I'll bundle these two slices into one commit, they're related." | "Related" is the agent's interpretation. Atomic commits give clean reverts. Two slices = two commits. |
| "The test is obvious, I'll add it after the implementation." | "After" never comes. Tests written alongside the code shape the design; tests written after confirm whatever was built. |
| "I'll skip the feature flag, the page is not visible yet." | "Not visible yet" is exactly when feature flags exist. Default OFF, toggle ON on user confirmation. |
| "I'll fix this typo I noticed in the adjacent file." | The typo will pollute the diff and mask the slice's real change. Note it, fix it in a separate slice. |
| "I'll commit on red just this once, the next slice will fix the test." | "Just this once" becomes routine. The next slice that depends on a red commit cannot be reverted independently. |
| "I'll skip the planning step, the slice is small." | "Small" slices are exactly the ones that silently grow. The 1-sentence plan takes 30 seconds and prevents scope creep. |
| "The slice is 350 lines but it's all one logical change." | 350 lines is review-fatigue territory. Split. The user (or future you) will thank you. |
| "I'll disable the failing test, it's flaky." | Flaky tests are real bugs (race conditions, missing waits). Investigate. Disabling is forbidden. |
| "I'll refactor this old code while I'm here, it's just a small cleanup." | Refactoring goes through `code-simplification`, separately. Mixing it with new feature work is forbidden. |
| "I'll do all the repositories first, then all the services." | Horizontal slicing produces no working software until the very end. Vertical slices give working software at every step. |
| "The cycle is overhead for this task." | The cycle *is* the value. Skipping it means skipping the discipline this skill exists to enforce. |

---

## Red Flags

### In the slicing

- A "slice" that is actually multiple slices bundled
- A slice >200 lines of net diff
- A slice touching >5 files
- A horizontal slice ("all repositories", "all types") instead of a vertical one
- A slice with no test
- A slice that introduces a public surface without a feature flag
- A slice that "depends on" the next slice to compile or test

### In the commit history

- A commit message bundling unrelated topics
- A commit on a red build (no `--no-verify` justification, no Ask First confirmation)
- A commit that touches files outside the slice's stated scope
- Two consecutive commits where the second one is "fix the previous commit"
- A revert that cannot be done cleanly because the commits are not atomic

### In the agent's behavior

- The agent skips the planning step
- The agent silently grows the slice mid-implementation
- The agent refactors adjacent code "while there"
- The agent disables a test to make the slice pass
- The agent batches multiple slices into one review
- The agent declares "done" without running the execution skill's Verification
- The agent starts a new slice while the previous is uncommitted

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Starting the planned first slice | **No** | Standard cycle |
| Planning the slices for a new task | **No** | "Always Do" |
| The planned slice grows past ~200 lines mid-implementation | **Yes** | Scope expansion |
| The planned slice grows past ~5 files mid-implementation | **Yes** | Scope expansion |
| Discovering an adjacent bug while implementing | **Yes** | Suspend slice, switch to debugging skill |
| Discovering adjacent code smell while implementing | **Yes** | Note for follow-up, do not fix in this slice |
| Skipping the test for "obvious" code | **Yes** (refuse: tests are mandatory) | Tests are non-negotiable |
| Adding a feature flag for the new endpoint | **No** | "Always Do" |
| Skipping the feature flag for an internal-only utility | **Yes** | Get confirmation |
| Removing a feature flag after rollout | **Yes** | Confirm rollout decision |
| Committing a green slice | **No** (suggest `commit-manager`) | Standard |
| Committing on a temporarily red build because the next slice fixes it | **Yes** | Confirm the gap |
| Reordering the planned slice sequence | **Yes** | Confirm order change |
| Splitting a planned slice into two smaller ones | **No** | Smaller is always allowed |
| Merging two planned slices into one | **Yes** | Confirm — usually wrong |
| Starting the next slice without committing the previous | **Yes** (refuse) | Forbidden |
| Pushing after the commit | **Yes** (refuse) | `commit-manager` forbids it |
| Running the full execution-skill Verification at the end | **No** | "Always Do" |

### Default rule

**Plan small. Test inside the slice. Commit on green. Stay in scope. The cycle is the value.**
