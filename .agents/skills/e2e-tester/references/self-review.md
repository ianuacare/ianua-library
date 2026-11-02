# E2E Tester — Self-Review Lens

Loaded on demand at step 8 of the Facilitator Workflow. Three tools to use before declaring "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation
2. **Red Flags** — observable signals in scenarios, reports, and execution
3. **Ask First decision aids** — concrete examples for the most fragile boundary tier

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The PRD doesn't cover this state, I'll write the scenario anyway." | Inventing acceptance criteria silently is the quickest way to invalidate the entire test suite. Flag the gap. |
| "The test passed, I don't need to write a report." | A passing test without a report cannot be referenced, audited, or re-validated. Always write the report. |
| "The screenshot is obvious, I'll skip it." | The screenshot is the proof that the test ran. Without it, "passed" is unverifiable. |
| "I'll just delete this flaky scenario from the suite." | Flaky scenarios point at real bugs (race conditions, missing waits). Investigate, do not delete. |
| "Re-run results — I'll just overwrite the old report." | History is the value of a report. Append, never overwrite. |
| "I'll skip the a11y check, this scenario is just about login." | Login forms are the most failed a11y scenario in production. Run the check. |
| "MCP is slower, I'll skip it and go straight to Playwright." | First-pass exploratory testing in MCP catches issues Playwright misses. Use the Decision Tree. |
| "I'll create the bug issue automatically since the test failed." | The user decides whether to file. Suggest, do not invoke. |
| "I'll use my real account credentials for the test." | Real PII in test data is a Never Do. Use synthetic. |
| "The test failed but it's environmental, I'll mark it skipped." | Environmental failures are still failures. Document the environment, do not hide the result. |
| "This scenario is too small to need test data documentation." | Reproducibility is the entire point. Document the data. |
| "I'll guess at the missing wireframe state." | Inventing UX silently. Flag to `ux-behaviour`. |

---

## Red Flags

### In scenarios

- A scenario without a `Source References` section linking PRD/FLOW/UC/WF
- Steps written in prose instead of Gherkin
- A scenario covering multiple unrelated journeys (split it)
- No `Preconditions` section
- No `Test Data` section
- No viewport specified
- "TBD" placeholders not resolved before execution
- Real PII (email addresses, phone numbers) in the data section

### In reports

- A report missing screenshots
- A report missing the environment section (URL, browser, viewport, data state)
- "Passed" status without supporting evidence
- A failed step with no reproduction details
- A report that has been edited rather than appended after a re-run
- Console errors logged but not analyzed
- A report that does not link the suite or scenarios it executed

### In the agent's behavior

- The agent invents acceptance criteria
- The agent runs a destructive scenario against production without confirming
- The agent auto-creates a GitHub issue for a failure
- The agent reports "all tests passed" without showing the report path
- The agent skips accessibility checks
- The agent edits a closed report
- The agent uses real user credentials

### In the running tests

- Tests that depend on a specific date/time (without freezing the clock)
- Tests that modify shared state and do not clean up
- Tests that depend on data from previous tests
- Long arbitrary `sleep()` waits instead of element-readiness waits
- Hardcoded element selectors that break on minor UI changes

---

## Ask First — decision aids

| Situation | Ask First? | Why |
|---|---|---|
| Running a smoke suite against `staging` | **No** | Standard pre-deploy check |
| Running a smoke suite against `production` | **Yes** | Confirm read-only and environment |
| Running a destructive scenario (creates orders) against `production` | **Yes (always)** | Confirm cleanup plan |
| Running a destructive scenario against `staging` with seed data | **No** | Standard |
| Filing a GitHub issue for a failed scenario | **Yes** | Suggest, never invoke |
| Adding a new scenario to an existing suite | **No** | In scope |
| Creating a new suite | **Yes** | Confirm naming and scope |
| Skipping a flaky scenario in the next run | **Yes** | Write `E2ED-NNN` documenting why |
| Switching from MCP to Playwright for an existing scenario | **Yes** | Write `E2ED-NNN` |
| Re-running a scenario after a fix | **No** | Standard fix-validation flow |
| Updating an issue status after a fix passes | **Yes** | Suggest, the user updates |
| Filling in a wireframe state that does not exist | **Yes** | Flag to `ux-behaviour` |
| Adding new test data fixtures | **No (synthetic only)** | Standard |
| Adding test data that contains real-looking emails | **Yes** | Confirm synthetic generation strategy |
| Increasing the test viewport size | **No** | In scope |
| Adding a new viewport profile | **Yes** | Project-wide change |

### Default rule

Suggest, never invoke. Derive from specs, never invent. Append to reports, never overwrite. When in doubt, ask the user before executing.
