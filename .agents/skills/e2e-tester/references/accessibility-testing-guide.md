# Accessibility Testing Guide

Lightweight a11y checks to perform opportunistically during E2E scenario execution. This is NOT a full accessibility audit — it covers the most impactful checks that can be verified during normal user journey testing.

## Checks During MCP Execution

When testing via claude-in-chrome, perform these checks as part of the normal flow:

### 1. Keyboard Navigation

- Complete the entire scenario using keyboard only (Tab, Enter, Space, Escape, Arrow keys)
- Verify that every interactive element (links, buttons, inputs, dropdowns) is reachable via Tab
- Verify that the tab order follows the visual reading order (left-to-right, top-to-bottom)
- Verify that modal dialogs trap focus (Tab does not leave the modal)
- Verify that Escape closes modals and dropdowns

### 2. Focus Indicators

- Every focused element must have a **visible** focus indicator (outline, border, highlight)
- Focus indicators must have sufficient contrast against the background
- Custom-styled elements (buttons, links) must not suppress the browser's default focus ring without providing an alternative

### 3. Form Labels and ARIA

- Every form input must have a visible label or `aria-label`
- Required fields must be indicated (visually and via `aria-required` or `required` attribute)
- Error messages must be associated with their field (via `aria-describedby` or adjacent text)
- Interactive elements without visible text must have `aria-label` (e.g., icon buttons)

### 4. Visual Inspection

- Text must be readable (sufficient size and contrast)
- Interactive elements must be large enough to click/tap (minimum 44x44px touch target)
- Content must not overflow or be hidden when zoomed to 200%
- Images with meaning must have alt text (check via page inspection)

## Checks During Playwright Execution

When testing via Playwright headless, use programmatic checks:

### With axe-core (if available)

```python
# Install: pip install axe-playwright-python
from axe_playwright_python.sync_playwright import Axe

axe = Axe()
results = axe.run(page)
violations = results.response["violations"]
```

Report violations with their severity (critical, serious, moderate, minor).

### Without axe-core (manual checks)

```python
# Check all images have alt text
images_without_alt = page.eval_on_selector_all(
    'img:not([alt])',
    'elements => elements.map(e => e.src)'
)

# Check all form inputs have labels
inputs_without_labels = page.eval_on_selector_all(
    'input:not([aria-label]):not([id])',
    'elements => elements.map(e => e.outerHTML)'
)

# Check for interactive elements with tabindex=-1
hidden_from_tab = page.eval_on_selector_all(
    '[tabindex="-1"]:not([role="presentation"])',
    'elements => elements.map(e => e.outerHTML)'
)
```

## Severity Classification

| Severity | Description | Example |
|----------|-------------|---------|
| **Critical** | Blocks users from completing the task | Form cannot be submitted via keyboard |
| **Major** | Significant barrier but workaround exists | Missing label on a required field |
| **Minor** | Inconvenience, does not block task completion | Focus indicator missing on one non-critical link |

## Reporting in Test Reports

a11y findings go in the **Accessibility Findings** section of the test report (RPT-NNN):

| Scenario | Finding | Severity | Details |
|----------|---------|----------|---------|
| E2E-001 | Submit button unreachable via Tab | Critical | Button has `tabindex="-1"`, keyboard users cannot submit the form |
| E2E-001 | Email field missing visible label | Major | Field has `placeholder` but no `<label>` or `aria-label` |

## WCAG 2.1 AA Reference

These checks map to the most impactful WCAG 2.1 Level AA success criteria:

- **1.1.1 Non-text Content**: images must have alt text
- **1.3.1 Info and Relationships**: form labels must be programmatically associated
- **2.1.1 Keyboard**: all functionality available via keyboard
- **2.4.3 Focus Order**: tab order must be logical
- **2.4.7 Focus Visible**: focus indicator must be visible
- **3.3.2 Labels or Instructions**: form inputs must have labels
- **4.1.2 Name, Role, Value**: interactive elements must have accessible names

For a full accessibility audit, consider dedicated tools (axe DevTools, Lighthouse, WAVE) or a specialist review. The checks in this guide cover the highest-impact criteria that are naturally verifiable during E2E user journeys.
