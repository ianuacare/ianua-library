# Test — Derive and Run E2E Scenarios

Derive E2E scenarios from product and UX specs, execute them in a browser, capture evidence, generate a structured test report.

**This command activates the `e2e-tester` skill.** Load and execute `.cursor/skills/e2e-tester/SKILL.md`.

The skill follows a facilitator workflow: it never invents acceptance criteria, derives every scenario from upstream artifacts (`PRD-NNN`, `FLOW-NNN`, `UC-NNN`, `WF-NNN`), uses Gherkin syntax, captures screenshots, and produces structured reports under `docs/specs/e2e/reports/`. It uses the Automation Decision Tree to choose between MCP (claude-in-chrome) and Playwright.

## Modes

- **Derive** — generate new scenarios from a PRD/flow/use case
- **Execute** — run an existing suite or list of scenarios in a browser
- **Re-validate** — re-run scenarios after a fix (always appends to the report, never overwrites history)

The skill asks which mode you want at the start.

## Prerequisites

- For derivation: a PRD or flow must exist (the skill will flag the gap and suggest `/spec` or `/design` if missing)
- For execution against production: explicit user confirmation required (Ask First boundary)

## Suggested next steps after /test

- For failures → suggest creating bug issues via `pm-github-workflow` (suggest only, never auto-invoke)
- After a fix → re-run the failing scenarios in re-validate mode
- For all-pass smoke runs → `/ship` (devops-aws-expert)
