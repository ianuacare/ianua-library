# Code Simplification — Self-Review Lens

Loaded on demand at the end of every simplification.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This code is obviously dead, I'll remove it." | "Obviously" is the agent's interpretation. Dead code may be reflected, dynamically loaded, exercised by integration tests, or used by an external tool. Verify with grep + git log + Ask First. |
| "I don't need to understand why this exists, it's clearly redundant." | Chesterton's Fence: do not remove a fence until you know why it was built. The "redundancy" may be a defense against a bug you do not see. |
| "I'll skip running the tests, the change is small." | "Small" changes regress most often, because they bypass scrutiny. Run the tests every time. |
| "I'll bundle these two refactors, they're related." | Bundling makes the diff hard to revert and impossible to bisect. One simplification per commit. |
| "I'll fix this small bug while I'm refactoring, no one will notice." | Mixing a bug fix with a refactor is a Never Do. Bug fix goes through `debugging-and-error-recovery`, separately. |
| "Tests are missing, I'll just refactor carefully." | "Carefully" is not a safety net. Write characterization tests first, in a separate commit, then refactor. |
| "Fewer lines is always simpler." | A 1-line nested ternary is *not* simpler than a 5-line if/else. Simplicity is about clarity, not line count. |
| "I'll extract this into a helper, it's used twice." | Two callers is borderline. Three callers is the rule of thumb. One caller is premature abstraction. |
| "I'll rename this exported function, the new name is clearer." | Renames touch every importer. Ask First. Then update all importers in the same commit. |
| "I'll move this file, it belongs in a different directory." | File moves break imports project-wide. Ask First. |
| "The comment says 'don't remove this', but I think it's wrong." | The comment is from someone who knew something you don't. Investigate before deleting. |
| "I'll add a `lodash` import to use one helper." | Almost never worth the dependency cost. Write the helper inline. |
| "I'll fix this typo in the variable name as part of the refactor." | Typo fixes are a separate change. Out of scope. |
| "The test failed after my refactor, I'll update the test." | The test failing is the proof that you changed behavior. Revert and re-plan. Never edit the test to match the refactor. |

---

## Red Flags

### In the planning

- The agent cannot explain why the original code exists
- The plan bundles multiple simplifications
- The plan touches code adjacent to the requested scope
- The plan introduces a new abstraction with one caller
- The plan adds a dependency
- The plan removes a comment without justification
- The plan changes a public API signature
- The plan moves files

### In the refactor

- A change that is not strictly behavior-preserving
- A `try { ... } catch {}` introduced "to make the test pass after refactor"
- A test edited to match the refactored code
- A test deleted to make the refactor pass
- A new helper function with no callers
- A dependency added to package.json / pyproject.toml
- Files modified outside the planned scope
- A commit that bundles the refactor with a typo fix or feature change

### In the verification

- The agent skips running the test suite before
- The agent skips running the test suite after
- The agent skips the execution skill's full Verification
- A test failure dismissed as "the test is wrong"
- "Untested code refactored carefully" — carefully is not a substitute for tests

### In the agent's behavior

- The agent removes code without verifying it is unused
- The agent renames a public symbol without checking importers
- The agent introduces a premature abstraction
- The agent simplifies code it does not understand
- The agent reports "done" without showing the test results
- The agent commits a refactor with a non-`refactor:` Conventional Commit prefix

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Removing an unused import | **No** | Standard hygiene |
| Removing a function that grep shows has zero callers | **Yes** | Could be reflected, dynamically loaded, used by tests |
| Removing a class that grep shows has zero references | **Yes** | Could be a base class, plugin, exported symbol |
| Removing a comment that says "TODO: handle X" | **Yes** | TODO is a backlog item; ask whether to handle X first |
| Removing a comment that explains *why* a non-obvious choice was made | **Yes (refuse first)** | Comments explain why; do not delete |
| Renaming a private variable inside one function | **No** | Local |
| Renaming a private function used in one file | **No** | Local |
| Renaming an exported function | **Yes** | Touches every importer |
| Renaming a class | **Yes** | Touches every importer |
| Splitting a 500-line file into two | **Yes** | File-layout change |
| Moving a file to a different directory | **Yes** | Import path change |
| Extracting a helper used in two places | **Yes** | Borderline; confirm "Three is the magic number" |
| Extracting a helper used in three or more places | **No** | Standard DRY |
| Introducing a new base class | **Yes** | New abstraction |
| Replacing if/else with switch (or vice versa) | **No** | Local equivalent rewrite |
| Replacing a for loop with a map/filter chain (or vice versa) | **No** (unless it changes complexity class) | Local |
| Inlining a constant used only once | **No** | Local |
| Extracting a constant used in many places | **No** | Standard |
| Reordering imports | **No** | Hygiene |
| Reordering function definitions in a file | **Yes** | Affects readability of the diff for reviewers |
| Reordering operations with side effects | **Yes** | May change behavior |
| Removing a `try/catch` that "looks redundant" | **Yes** | May hide a real edge case |
| Adding a dependency to enable the simplification | **Yes (refuse first)** | Almost always wrong |
| Writing characterization tests for untested code before refactoring | **No** | "Always Do" — required first step |
| Refactoring untested code without characterization tests | **Yes (refuse)** | Forbidden |
| Running the test suite before the refactor | **No** | "Always Do" |
| Running the test suite after the refactor | **No** | "Always Do" |
| Skipping the test suite because "it's a one-line rename" | **Yes (refuse)** | Forbidden |
| Bundling two refactors into one commit | **Yes (refuse)** | Forbidden |
| Bundling a refactor with a bug fix | **Yes (refuse)** | Forbidden |
| Committing the refactor via `commit-manager` | **No** (suggest) | Standard |

### Default rule

**Understand first. Preserve behavior. Test before AND after. One simplification per commit. When in doubt, do not change. Chesterton's Fence is the law.**
