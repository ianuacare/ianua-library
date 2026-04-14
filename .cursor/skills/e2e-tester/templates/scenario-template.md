# {E2E-NNN} — {Scenario Title}

| Field | Value |
|-------|-------|
| **Author** | {name} |
| **Date** | {YYYY-MM-DD} |
| **Status** | Draft / Active / Deprecated / Superseded by E2E-NNN |
| **Suite** | {SUITE-NNN if assigned} |
| **Automation** | MCP / Playwright / Manual |
| **Priority** | Critical / High / Normal / Low |

## Source References

- PRD: {PRD-NNN-slug if applicable}
- User flow: {FLOW-NNN-slug if applicable}
- Use case: {UC-NNN-slug if applicable}
- Wireframe: {WF-NNN-slug if applicable}
- Component spec: {CMP-NNN-slug if applicable}
- GitHub issue: {#N if applicable}

## Description

{What user journey does this scenario verify? What is the expected end-to-end behavior?}

## Preconditions

- {Application state required before the scenario starts}
- {User authentication state}
- {Test data requirements}

## Scenario: {Scenario Name}

```gherkin
Given {initial context / state}
  And {additional context if needed}
When {action the user takes}
  And {additional action if needed}
Then {expected observable outcome}
  And {additional assertion if needed}
```

## Alternative Scenario: {Variant Name}

```gherkin
Given {different initial context}
When {same or different action}
Then {different expected outcome}
```

## Accessibility Checks

- [ ] Keyboard navigation completes the flow without mouse
- [ ] Focus indicators visible on all interactive elements
- [ ] Screen reader labels present on form inputs and buttons
- [ ] Tab order follows the visual reading order
- [ ] {scenario-specific a11y check}

## Viewport Coverage

| Viewport | Required? | Notes |
|----------|-----------|-------|
| Desktop (1280x720) | Yes | Primary test viewport |
| Mobile (375x812) | {Yes/No} | {notes} |
| Tablet (768x1024) | {Yes/No} | {notes} |

## Test Data

| Data | Value / Source | Cleanup required? |
|------|---------------|-------------------|
| {user account} | {test user or fixture} | {Yes/No} |
| {input data} | {description} | {Yes/No} |

## Notes

{Any additional context, known limitations, flaky conditions, or dependencies on external services}
