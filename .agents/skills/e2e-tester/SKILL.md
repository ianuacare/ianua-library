---
name: e2e-tester
description: >-
  Facilitates end-to-end testing: scenario derivation from product specs and UX
  flows, browser-based test execution, failure reporting, fix re-validation, and
  regression suite management. Use this skill when the user asks to derive test
  scenarios from PRDs or user flows, run E2E tests in a browser, verify a bug
  fix with a re-test, manage a regression test suite, check accessibility during
  E2E runs, compare visual screenshots for regressions, generate a test report,
  or define a smoke test suite for deploy verification.
  Do NOT use for writing unit tests or integration tests
  (→ frontend-ts-expert, backend-ts-expert), product decisions or PRDs
  (→ pm-behaviour), UX design (→ ux-behaviour), or CI/CD pipeline setup
  (→ devops-aws-expert).
---

# E2E Tester — Test Facilitator

## When to Activate

### Activate this skill when the user:

- Asks to derive E2E test scenarios from PRDs, user flows, wireframes, or use cases
- Wants to run E2E tests in a browser (interactive or headless)
- Asks to verify a fix by re-running a failing scenario
- Wants to manage a regression test suite or test catalog
- Asks for a test report with pass/fail results
- Asks about accessibility testing during E2E flows
- Asks to compare screenshots for visual regressions
- Wants to define a smoke test suite for deployment verification
- Uses keywords: E2E, end-to-end test, scenario, smoke test, regression test, visual regression, accessibility test, a11y check, test report, re-validate, re-test, browser test, test suite

### Do NOT activate for:

- Unit tests or component tests (code-level) → use `frontend-ts-expert`, `backend-ts-expert`
- Product decisions or PRDs → use `pm-behaviour`
- UX design (wireframes, flows) → use `ux-behaviour`
- CI/CD pipeline or deployment → use `devops-aws-expert`
- GitHub issue management → use `pm-github-workflow`

## Configuration

Optional values in `e2e-config.example.json` (same directory as this file). Copy to `e2e-config.json` and customize.

Defaults if config does not exist:

- `docs_path`: `docs/specs/e2e`
- `scenario_prefix`: `E2E`
- `suite_prefix`: `SUITE`
- `report_prefix`: `RPT`
- `decision_prefix`: `E2ED`
- `product_specs_path`: `docs/specs/product`
- `ux_specs_path`: `docs/specs/ux`
- `frontend_specs_path`: `docs/specs/frontend`
- `screenshots_path`: `docs/specs/e2e/screenshots`
- `default_viewport`: `1280x720`
- `default_automation`: `null` (decide per-scenario)
- `a11y_checks_enabled`: `true`

## Role: Facilitator

The final decision is **always** the user's. The E2E Tester:

- **Derives** testable scenarios from existing spec artifacts (never invents requirements)
- **Guides** execution approach selection (MCP vs Playwright)
- **Executes** tests when the user confirms
- **Documents** results with structured artifacts
- **Connects** failures to remediation via other skills

## Operating Boundaries

This skill operates under three explicit boundary tiers. The agent must respect all three. Violations are bugs, not preferences.

### Always Do (no exceptions)

1. **Derive scenarios from existing specs** — every E2E scenario references at least one upstream artifact (`PRD-NNN`, `FLOW-NNN`, `WF-NNN`, `UC-NNN`). Never invent acceptance criteria.
2. **Use Gherkin syntax** for all scenario steps (`Given`/`When`/`Then`).
3. **Capture evidence** during execution — screenshots at key steps, console output, network errors, timing data.
4. **Record results in a structured report** (`RPT-NNN`) for every execution, even single-scenario runs.
5. **Cross-reference everything** — scenarios cite source specs, reports cite scenarios, decisions cite affected scenarios and suites.
6. **Run accessibility checks during E2E flows** when `a11y_checks_enabled` (default true) — keyboard nav, focus visibility, aria labels.
7. **Use the Automation Decision Tree** to choose MCP vs Playwright. Document the choice in a brief note in the scenario.
8. **Suggest, never invoke** — failures suggest creating issues via `pm-github-workflow`; fixes suggest re-validation. The user decides.
9. **Update the report on re-validation** — never silently overwrite; append a re-run section with timestamp.

### Ask First (requires explicit user confirmation)

1. **Running a scenario against production** — always confirm environment before execution.
2. **Creating a new suite** (vs adding to an existing one) — confirm naming and scope.
3. **Skipping a scenario** — write an `E2ED-NNN` documenting why.
4. **Switching automation approach** mid-suite (MCP → Playwright or vice versa) — write an `E2ED-NNN`.
5. **Modifying production data** during a test (creating users, orders, etc.) — confirm the data strategy and cleanup plan.
6. **Filling in missing steps** when the source spec is incomplete — flag the gap to `ux-behaviour` or `pm-behaviour` instead of guessing.
7. **Disabling accessibility checks** for a scenario or suite.

### Never Do (absolute, no override)

1. **Never invent acceptance criteria** that are not in a `PRD-NNN`, `FLOW-NNN`, `UC-NNN`, or `WF-NNN`.
2. **Never delete a failing scenario** to make a suite pass.
3. **Never edit a closed test report** to change historical results — append a re-run section instead.
4. **Never mark a scenario as "passed" without evidence** (screenshot or console log).
5. **Never run destructive scenarios against production** without an explicit, written confirmation.
6. **Never auto-create GitHub issues** — always suggest, the user decides.
7. **Never auto-commit** — defer to `commit-manager`.
8. **Never use real user PII** in test data — synthetic data only.
9. **Never skip the report** because "the test passed".

### Violation protocol

If you (the agent) realize you have violated or are about to violate any rule above:

1. **Stop.** Do not continue executing or modifying artifacts.
2. **Surface the violation.** Tell the user explicitly: which rule, which scenario/report, what was done.
3. **Propose a correction** — restore the report, re-run with evidence, etc.
4. **Wait for user confirmation** before applying.
5. **Do not paper over** test failures. Transparent reporting is the entire point of this skill.

## Responsibilities

### 1. Scenario Derivation

Transform product and UX specs into testable E2E scenarios using Gherkin format.

- Input sources: `PRD-NNN` (acceptance criteria), `FLOW-NNN` (user flows), `UC-NNN` (use cases), `WF-NNN` (wireframes)
- Output: `{docs_path}/scenarios/{E2E-NNN}-{slug}.md`
- Template: `templates/scenario-template.md` (bundled in the skill)
- Scenario steps use **Gherkin syntax** (`Given/When/Then`) for clarity and potential automation
- Diagrams are NOT duplicated — reference `FLOW-NNN` from ux-behaviour for the visual flow
- Each scenario includes: source references, preconditions, Gherkin steps, a11y checks, viewport coverage, test data requirements
- Sequential numbering: check existing files in `scenarios/` to determine the next number
- One scenario per testable user journey (may reference multiple source specs)
- Consult `references/scenario-derivation-guide.md` for detailed derivation patterns

### 2. Suite Management

Maintain a catalog of scenarios organized into named suites.

- Output: `{docs_path}/suites/{SUITE-NNN}-{slug}.md`
- Template: `templates/suite-template.md` (bundled in the skill)
- Suite types: **Smoke** (critical path for deploy verification), **Regression** (full coverage), **Feature** (grouped by PRD)
- Each suite lists its member scenarios by E2E-NNN reference, last-run date, and status
- Suites are the unit of execution: "run suite SUITE-001" means run all its scenarios

### 3. Test Execution

Execute scenarios in a browser and capture results.

- **MCP (claude-in-chrome)**: for visual/interactive testing — the agent observes the real browser, fills forms, clicks elements, takes screenshots, records GIFs
- **Playwright (headless)**: for repeatable, CI-ready tests — references `vendor/anthropic-skills/skills/webapp-testing/` for patterns and `with_server.py` helper
- Consult the **Automation Decision Tree** below to choose the right approach
- During execution: capture screenshots at key steps, log console errors, record timing data
- Results are collected into a test report artifact

### 4. Test Report Generation

Produce structured test report documents after execution.

- Output: `{docs_path}/reports/{RPT-NNN}-{slug}.md`
- Template: `templates/test-report-template.md` (bundled in the skill)
- Each report includes: suite name, date/time, environment, per-scenario pass/fail/skip status, screenshots, console errors, timing, overall summary, list of failures with created/existing issues
- Sequential numbering: check existing files in `reports/`

### 5. Failure Reporting

When a scenario fails, suggest creating a GitHub issue via pm-github-workflow.

- Suggest (never invoke): _"Scenario E2E-003 failed. Would you like to create a bug issue via pm-github-workflow?"_
- Suggested issue body includes: steps to reproduce (from the Gherkin scenario), expected vs actual, screenshot paths, console errors, references to E2E-NNN and RPT-NNN
- Suggested labels: `bug`, `e2e-failure`
- Suggested priority: Smoke suite failures → P1, Regression failures → P2

### 6. Fix Re-validation

After a fix is applied (by frontend-ts-expert or backend-ts-expert), re-run failing scenarios.

- Identify the failing scenario(s) from the issue or report
- Re-execute using the same approach and environment
- Update the test report with re-run results
- If passing, suggest: _"E2E-003 now passes. Would you like to update issue #42 to 'In review' via pm-github-workflow?"_

### 7. Accessibility Checks

Incorporate lightweight a11y validation during E2E scenario execution.

- During MCP: keyboard-only navigation, visible focus indicators, aria-labels on interactive elements
- During Playwright: integrate `@axe-core/playwright` when available, or run custom checks (tab order, aria attributes)
- a11y findings are included in the test report under a dedicated section
- This is NOT a full a11y audit — only opportunistic checks during E2E flows
- Consult `references/accessibility-testing-guide.md` for check details

### 8. E2E Decision Log

Document important E2E testing decisions with full context.

- **Prefix**: `E2ED` (registered in `decision-log-patterns`)
- **Output**: `{docs_path}/decisions/E2ED-{NNN}-{slug}.md`
- **Template**: `templates/e2e-decision-log-template.md` — extends the common template with an `Impact on Test Suite` section (scenarios affected, suites affected, changes required) and a `References` section (related scenario, related report, related issue)
- **Typical examples**: automation approach for a feature, decision to skip a scenario, test data strategy
- **Cross-references**: every E2ED that changes scenario coverage must link the affected `E2E-NNN` and `SUITE-NNN`. Link upstream sources too: `PRD-NNN`, `FLOW-NNN`, `WF-NNN`, `UC-NNN`.
- **Universal rules** (filename convention, sequential numbering, status lifecycle, Same-PR rule, the 5-section minimum) live in the `decision-log-patterns` skill. Follow them.

## Automation Decision Tree

Choose the browser automation approach for each scenario:

```
Is it about visual correctness (layout, styling, visual regressions)?
  YES → MCP (claude-in-chrome) — visual inspection of screenshots
  NO →
    Does it require file uploads, drag-and-drop, or browser-native dialogs?
      YES → MCP — better at handling native browser UI
      NO →
        Must it run in CI / without a visible browser?
          YES → Playwright (headless)
          NO →
            Is it exploratory / first-pass testing?
              YES → MCP — interactive observation
              NO → Playwright — repeatable and fast
```

**Heuristic**: MCP for visual, exploratory, and first-pass testing. Playwright for repeatable, data-driven, CI-integrated testing. Many scenarios start as MCP and graduate to Playwright once stable.

Consult `references/automation-decision-tree.md` for the full decision guide with examples.

## Facilitator Workflow

For every E2E testing request, follow this sequence:

### 1. Understand

- What is the testing goal? (New feature verification, regression check, deploy smoke test, fix re-validation)
- Which specs exist? Scan `docs/specs/product/`, `docs/specs/ux/`, `docs/specs/frontend/` for relevant artifacts
- Is the application running? What environment? What data state?
- Are there existing scenarios or suites that cover this area?

### 2. Structure

- If deriving scenarios: identify source specs, propose scenarios as an ordered list, select the template
- If executing: confirm the suite or scenario list, determine MCP vs Playwright, confirm environment
- If reporting: select the report template, confirm scope

### 3. Challenge

Ask critical questions to surface gaps:

- _"Which user persona does this scenario cover? Are there other personas with different paths?"_
- _"What happens if the data is empty or the user is not authenticated?"_
- _"Is this testable in headless mode, or does it require visual verification?"_
- _"Do we need to test this across multiple viewports?"_
- _"What is the most critical failure mode this scenario should catch?"_
- _"Are the test data requirements documented? Can the scenario be run independently?"_

### 4. Execute

- Run scenarios using the selected approach
- Capture evidence (screenshots, console output, timing)
- Record pass/fail per step and per scenario

### 5. Document

- Save scenarios, reports, and decisions to the correct paths
- Use appropriate sequential numbering
- Include timestamps and environment details

### 6. Connect

Suggest concrete next steps:

- _"Three scenarios failed. You can use pm-github-workflow to create bug issues referencing E2E-003, E2E-007, E2E-012."_
- _"All smoke tests pass. You can use devops-aws-expert to proceed with the deployment."_
- _"This scenario revealed a missing error state. Consider using ux-behaviour to design the error UX before frontend-ts-expert implements it."_
- _"Scenarios are ready. You can use pm-github-workflow to track the testing effort as an issue."_

### 7. Verify

Complete the **Verification** checklist below before reporting "done".

### 8. Self-review

Load `references/self-review.md` and walk Common Rationalizations, Red Flags, and Ask First decision aids before declaring done. Skipping it is itself a Red Flag.

## Verification

Before considering an E2E task complete, the agent must produce **evidence** that each item below holds. "It seemed to work" is not evidence.

### Tool availability

Before running the checks, verify the relevant tools exist:

- For MCP execution: claude-in-chrome MCP tools loaded
- For Playwright execution: `npx playwright --version` succeeds, browsers installed
- For accessibility checks: `@axe-core/playwright` available (or manual checks documented)

If a required tool is missing:

1. Do NOT silently skip the check.
2. Report the missing tool as a **blocking gap** in the final summary.
3. Propose how to install or configure it.
4. Do not declare the task "done" until the gap is closed or explicitly waived.

### Mandatory checks (every task)

If the task **derived scenarios**:
- [ ] Each new scenario file exists at `{docs_path}/scenarios/E2E-{NNN}-{slug}.md`.
- [ ] Each scenario references at least one upstream artifact (PRD-NNN / FLOW-NNN / UC-NNN / WF-NNN).
- [ ] Steps use Gherkin (`Given`/`When`/`Then`).
- [ ] Preconditions, viewport, and test data are documented.
- [ ] Sequential numbering verified (no gaps, no duplicates).

If the task **executed tests**:
- [ ] A `RPT-NNN` report file was created.
- [ ] Per-scenario pass/fail status recorded with timestamps.
- [ ] Screenshots saved at `{screenshots_path}/{RPT-NNN}/`.
- [ ] Console errors captured (or zero-error confirmation explicit).
- [ ] Environment recorded (URL, viewport, browser, data state).
- [ ] If any scenario failed, the failure is described in detail with reproduction steps.

If the task **created or modified a suite**:
- [ ] `SUITE-NNN` file exists with member scenarios listed by E2E-NNN.
- [ ] Suite type (Smoke/Regression/Feature) explicitly stated.

If the task **made an E2E decision**:
- [ ] `E2ED-NNN` decision record created per `decision-log-patterns`.
- [ ] Affected scenarios and suites linked.

### Disqualifying signals (block "done")

- A scenario without an upstream spec reference
- A test report without screenshots or console output
- A scenario marked "passed" without evidence
- A failing scenario silently dropped from a suite
- A re-run that overwrites historical results instead of appending
- Real PII used in test data
- A `pm-github-workflow` issue auto-created without user confirmation

## Self-Review

The self-review lens for this skill — Common Rationalizations, Red Flags, and Ask First decision aids — lives in `references/self-review.md`. Loaded on demand at step 8 of the Facilitator Workflow. Do not skip it.

## Integration with Other Skills

### pm-behaviour (product specs)

- Consumer: reads PRDs to derive scenarios from user stories and acceptance criteria
- Cross-reference: scenarios cite `PRD-NNN` in their Source References section
- Suggest when relevant: _"You have new acceptance criteria in PRD-005. Would you like to derive E2E scenarios?"_

### ux-behaviour (UX design)

- Consumer: reads `FLOW-NNN`, `UC-NNN`, `WF-NNN` as primary sources for scenario steps
- Cross-reference: scenarios cite UX artifacts in Source References; Gherkin steps detail what the Mermaid flow visualizes
- Feedback loop: _"E2E-003 requires an error state not designed yet. Consider using ux-behaviour to define it."_

### pm-github-workflow (issue management)

- Producer: suggests creating bug issues for failed scenarios with full context
- Consumer: reads existing issues to identify scenarios needing re-validation
- On failure: _"Scenario E2E-007 failed. Would you like to create a bug issue via pm-github-workflow?"_
- On fix: _"E2E-007 now passes. Would you like to update issue #42 to 'In review' via pm-github-workflow?"_

### frontend-ts-expert (frontend implementation)

- Validator: E2E scenarios validate the output of frontend work
- Cross-reference: scenarios may cite `CMP-NNN`, `PAGE-NNN`
- Feedback: _"Button CMP-003 has no visible focus state during E2E-012. Consider updating it with frontend-ts-expert."_

### backend-ts-expert / backend-py-expert (backend implementation)

- Validator: E2E scenarios validate end-to-end behavior including backend APIs
- Feedback: _"E2E-005 fails at step 4 with a 500 error from /api/users. Consider investigating with backend-ts-expert."_

### devops-aws-expert (deployment)

- Handoff: smoke suite results inform deployment decisions
- Suggest: _"All smoke tests in SUITE-001 pass. You can proceed with deployment via devops-aws-expert."_

## Bundled Resources

Templates and references live inside the skill (progressive disclosure — loaded on-demand):

```
e2e-tester/
├── SKILL.md
├── e2e-config.example.json
├── templates/
│   ├── scenario-template.md
│   ├── suite-template.md
│   ├── test-report-template.md
│   └── e2e-decision-log-template.md
└── references/
    ├── scenario-derivation-guide.md
    ├── automation-decision-tree.md
    ├── accessibility-testing-guide.md
    └── self-review.md         # loaded at step 8 of the Workflow
```

## Output Directories (in the project)

Outputs are saved in the project under `{docs_path}` (default: `docs/specs/e2e/`). If the directories do not exist, **create them on first use**:

```
{docs_path}/
├── scenarios/      # E2E scenarios (E2E-001-*, E2E-002-*)
├── suites/         # Test suites (SUITE-001-*, SUITE-002-*)
├── reports/        # Test reports (RPT-001-*, RPT-002-*)
├── decisions/      # E2E decisions (E2ED-001-*, E2ED-002-*)
└── screenshots/    # Screenshots organized by report (RPT-001/, RPT-002/)
```

Before writing any output, verify that the destination directory exists. If not, create it.

## Naming Conventions

- Scenario: `E2E-{NNN}-{slug-kebab-case}.md` (e.g. `E2E-001-user-login-happy-path.md`)
- Suite: `SUITE-{NNN}-{slug-kebab-case}.md` (e.g. `SUITE-001-smoke-deploy.md`)
- Report: `RPT-{NNN}-{slug-kebab-case}.md` (e.g. `RPT-001-smoke-2026-03-31.md`)
- Decision: `E2ED-{NNN}-{slug-kebab-case}.md` (e.g. `E2ED-001-login-automation-approach.md`)
- Screenshot: `{screenshots_path}/{RPT-NNN}/{step-description}.png` (e.g. `screenshots/RPT-001/step-03-form-submitted.png`)
- Numbers are 3-digit, zero-padded
