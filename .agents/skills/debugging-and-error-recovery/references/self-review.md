# Debugging and Error Recovery — Self-Review Lens

Loaded on demand at the end of every triage.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The stack trace points to line 47, the bug is there." | The stack trace points to where the symptom surfaced. Often the root cause is upstream in the call chain. Read it skeptically. |
| "I can't reproduce it but I think I know the fix." | "Think" is not "know". A fix you cannot test is a fix that does not exist. Reproduce first. |
| "Adding a retry will mask the flakiness." | Retries hide root causes (race conditions, timing assumptions). Find the cause. |
| "I'll wrap this in try/catch to make the test pass." | Silently swallowed errors guarantee the bug returns somewhere worse. Type the error and handle it explicitly. |
| "The user said 'sometimes it fails', that's enough to start." | "Sometimes" is not a reproduction. Ask for the steps, the data, the environment. |
| "It works on my machine." | Environment differences are real bugs. Find which difference matters. |
| "The test is flaky, I'll mark it skip." | Flaky tests are race conditions. Investigate. Skipping ships the bug. |
| "I'll skip the regression test, the fix is obvious." | "Obvious" fixes regress when someone else touches the code. The test is the lock. |
| "The error message says 'connection refused', it's the network." | Error messages from libraries are often misleading. Verify the actual cause. |
| "I'll bisect later, let me try a guess first." | Guessing wastes hours. Bisecting takes minutes. Bisect first. |
| "I'll commit the fix and the cleanup together, the diff is small." | Cleanup hides the fix. The fix commit must be minimal and reviewable on its own. |
| "I'll close the bug, I cannot reproduce it after 3 tries." | Three tries is not exhaustion. Capture more data and try again, or document the gap explicitly. |
| "The fix worked locally, I'll skip running the full test suite." | "Worked locally" is not "works in CI". Run the full suite. |
| "The bug is too complex to write a test for." | Then the code is too complex to understand. Reduce it first. |

---

## Red Flags

### In the reproduction

- A bug report without environment details (OS, version, runtime)
- A bug report with no reproduction steps
- A "fix" proposed before reproduction
- A reproduction that requires "sometimes" or "occasionally"
- A reproduction that depends on a specific time, day, or user
- A reproduction whose minimum size has not been reduced

### In the localization

- "The bug is somewhere in the auth flow"
- A localization that points to the stack trace's top frame without verifying upstream
- Adding logs in dozens of files instead of bisecting
- Skipping `git bisect` for a regression bug
- Trusting an external service's error message without verifying

### In the fix

- A `try { ... } catch {}` block added "to handle this case"
- A retry loop added without understanding the underlying flakiness
- A `setTimeout` / `sleep` added to "fix the race condition"
- A test disabled or deleted to make the build green
- A production-data mutation done without backup
- A fix that makes the test pass but does not explain the root cause
- A commit that bundles the fix with unrelated cleanup
- A fix that touches more than the minimum needed code
- An unexplained "I changed this and now it works"

### In the guard step

- No regression test added
- A regression test that does not actually fail before the fix
- A regression test added in a separate commit "for cleanliness"
- A regression test that exercises the fix but not the original bug condition
- No mention in the commit message of what was wrong
- No mention of the test that was added

### In the agent's behavior

- The agent skips reproduction
- The agent proposes a fix in the first message before triage
- The agent reaches for retries or try/catch instead of root cause
- The agent declares "fixed" without re-running the failing test
- The agent declares "cannot reproduce" too quickly
- The agent modifies production data without Ask First confirmation
- The agent fixes the bug and refactors adjacent code in the same commit

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Adding logs in source code to investigate | **No** | Standard, but clean them up before commit |
| Adding logs in production code that may capture PII | **Yes** | Confirm redaction strategy |
| Increasing log verbosity in production | **Yes** | Cost and noise impact |
| Bisecting recent commits (≤50) | **No** | Standard |
| Bisecting more than 50 commits | **Yes** | Time investment |
| Reverting a commit that looks like the cause | **Yes** | Confirm before reverting |
| Rolling back a deployment | **Yes** | Confirm rollback target |
| Modifying production data to fix a state issue | **Yes (always)** | Backup first, confirm |
| Writing a regression test for the bug | **No** | "Always Do" |
| Disabling a test to bypass the bug | **Yes (refuse first)** | Forbidden by default |
| Deleting a test | **Yes (refuse first)** | Forbidden by default |
| Closing a bug as "not reproducible" | **Yes** | Document the gap |
| Re-running the failing test after the fix | **No** | "Always Do" |
| Re-running the full execution-skill Verification after the fix | **No** | "Always Do" |
| Skipping the Verification because "it's a one-line fix" | **Yes (refuse)** | Forbidden |
| Suggesting a `DEC-NNN` for an architectural weakness | **No** | Suggesting is fine |
| Auto-creating a `DEC-NNN` for the user | **Yes (refuse)** | User decides |
| Suggesting `code-simplification` for the surrounding code | **No** | Suggesting is fine |
| Refactoring the surrounding code in the same commit as the fix | **Yes (refuse)** | Forbidden — separate commit |
| Committing the fix via `commit-manager` | **No** (suggest) | Standard |
| Pushing the fix | **Yes (refuse)** | Out of scope |

### Default rule

**Reproduce first. Localize second. Reduce third. Fix fourth. Guard fifth. Skip no step. Trust no error message blindly. Every bug becomes a test.**
