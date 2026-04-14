# {SUITE-NNN} — {Suite Name}

| Field | Value |
|-------|-------|
| **Author** | {name} |
| **Date** | {YYYY-MM-DD} |
| **Status** | Active / Deprecated |
| **Type** | Smoke / Regression / Feature |
| **Estimated duration** | {minutes} |

## Purpose

{What does this suite verify? When should it be run? (e.g., before every deploy, after a feature merge, weekly regression)}

## Scenarios

| # | Scenario | Priority | Automation | Last Run | Last Result |
|---|----------|----------|------------|----------|-------------|
| 1 | E2E-{NNN}-{slug} | Critical | Playwright | {date} | Pass / Fail / Skip |
| 2 | E2E-{NNN}-{slug} | High | MCP | {date} | Pass / Fail / Skip |

## Execution Order

{Are scenarios independent or must they run in a specific order? Describe any dependencies between scenarios.}

## Environment Requirements

- {Server URL or start command}
- {Required services (database, cache, external APIs)}
- {Test data fixtures or seed scripts}

## Run History

| Date | Report | Pass | Fail | Skip | Duration |
|------|--------|------|------|------|----------|
| {date} | RPT-{NNN} | {n} | {n} | {n} | {minutes} |

## References

- Related PRD: {PRD-NNN if this suite covers a specific feature}
- Related release: {release plan if this is a release smoke suite}
