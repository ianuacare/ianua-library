# Automation Decision Tree

How to choose between MCP (claude-in-chrome) and Playwright (headless) for each E2E scenario.

## Decision Tree

```
Is the scenario about visual correctness (layout, styling, visual regressions)?
│
├─ YES → Use MCP
│        The agent can visually inspect screenshots and compare layouts.
│        Examples: verifying responsive design, checking alignment, spotting visual bugs.
│
└─ NO →
    Does the scenario require file uploads, drag-and-drop, or browser-native dialogs?
    │
    ├─ YES → Use MCP
    │        MCP handles native browser UI more reliably through direct interaction.
    │
    └─ NO →
        Must the scenario run in CI / without a visible browser?
        │
        ├─ YES → Use Playwright (headless)
        │        Playwright runs without a display and integrates with CI pipelines.
        │        Reference: vendor/anthropic-skills/skills/webapp-testing/
        │
        └─ NO →
            Is this exploratory / first-pass testing of a new feature?
            │
            ├─ YES → Use MCP
            │        Interactive observation helps discover unexpected behaviors.
            │        Record a GIF for documentation.
            │
            └─ NO →
                Is repeatability and speed the priority?
                │
                ├─ YES → Use Playwright
                │        Faster execution, deterministic, scriptable.
                │
                └─ NO → Use MCP (default for manual/ad-hoc testing)
```

## Summary Heuristic

| Factor | MCP | Playwright |
|--------|-----|------------|
| Visual verification | Best | Limited (screenshot comparison only) |
| Form automation | Good | Better (more reliable selectors) |
| Native browser UI | Better | Limited |
| CI integration | Not possible | Designed for it |
| Exploratory testing | Best | Not suitable |
| Repeatability | Lower (agent-driven) | Higher (scripted) |
| Speed | Slower | Faster |
| GIF recording | Built-in | Not available |
| Accessibility checks | Visual + keyboard | axe-core integration |

## Scenario Graduation Path

Many scenarios follow a natural progression:

1. **MCP first** — exploratory testing of a new feature, discovering selectors and behaviors
2. **Document as Gherkin** — capture the steps and expected outcomes
3. **Graduate to Playwright** — once the scenario is stable, convert to a headless script for CI

This is not mandatory. Some scenarios remain MCP-only (visual testing) and some start as Playwright (well-defined, data-driven flows).

## MCP Execution Pattern

When executing via MCP (claude-in-chrome):

1. Call `tabs_context_mcp` to check current browser state
2. Create a new tab with `tabs_create_mcp` or navigate with `navigate`
3. Use `read_page` or `get_page_text` to verify page content
4. Use `form_input` for filling forms
5. Use `computer` for clicks and interactions
6. Use `read_page` with screenshots to capture visual evidence
7. Use `gif_creator` for multi-step interaction recording
8. Use `read_console_messages` to check for JavaScript errors
9. Use `read_network_requests` to monitor API calls

## Playwright Execution Pattern

When executing via Playwright (headless):

1. Reference `vendor/anthropic-skills/skills/webapp-testing/` for patterns
2. If the server is not running, use `scripts/with_server.py` for lifecycle management
3. Write a Python script using `sync_playwright()`
4. Always `page.wait_for_load_state('networkidle')` before inspecting DOM
5. Use descriptive selectors: `text=`, `role=`, CSS selectors, or IDs
6. Capture screenshots with `page.screenshot(path=...)`
7. Capture console errors with `page.on('console', ...)`
8. Always `browser.close()` when done

## When Both Approaches Are Needed

Some scenarios benefit from both:

- **MCP for visual verification** of the UI appearance
- **Playwright for data-driven validation** of the same flow with multiple inputs

In this case, create one scenario with `Automation: Mixed` and note which steps use which approach.
