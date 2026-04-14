# {RPT-NNN} — {Report Title}

| Field | Value |
|-------|-------|
| **Date** | {YYYY-MM-DD HH:MM} |
| **Suite** | {SUITE-NNN-slug} |
| **Environment** | {URL / local / staging / production} |
| **Automation** | {MCP / Playwright / Mixed} |
| **Viewport** | {width}x{height} |

## Summary

| Total | Passed | Failed | Skipped | Duration |
|-------|--------|--------|---------|----------|
| {n} | {n} | {n} | {n} | {duration} |

## Results

### Passed

| Scenario | Duration | Notes |
|----------|----------|-------|
| E2E-{NNN}-{slug} | {seconds} | |

### Failed

| Scenario | Failed Step | Expected | Actual | Screenshot | Console Errors |
|----------|------------|----------|--------|------------|----------------|
| E2E-{NNN}-{slug} | {Gherkin step text} | {expected outcome} | {actual outcome} | {path to screenshot} | {errors or "None"} |

### Skipped

| Scenario | Reason |
|----------|--------|
| E2E-{NNN}-{slug} | {reason for skipping} |

## Accessibility Findings

| Scenario | Finding | Severity | Details |
|----------|---------|----------|---------|
| E2E-{NNN} | {finding description} | Critical / Major / Minor | {details and remediation hint} |

## Performance Observations

| Scenario | Page | Load Time | LCP | Notes |
|----------|------|-----------|-----|-------|
| E2E-{NNN} | {page URL} | {ms} | {ms} | {notes} |

## Issues Created / Updated

| Issue | Title | Status | Scenario |
|-------|-------|--------|----------|
| #{N} | {title} | New / Updated | E2E-{NNN} |

## Screenshots

Screenshots stored in: `{screenshots_path}/{RPT-NNN}/`

## Re-run Information

| Field | Value |
|-------|-------|
| **Is re-run** | Yes / No |
| **Previous report** | {RPT-NNN if this is a re-run} |
| **Trigger** | {fix applied in issue #N / scheduled regression / manual} |

## Next Steps

- {Recommended actions based on results}
