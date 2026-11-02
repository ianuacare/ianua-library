# Testing strategy (frontend)

## Coverage

- Meet or exceed **`min_coverage_pct`** from `frontend-config.json` (default **80%**).
- After adding or changing UI code, **run the project's coverage command** and add tests until the threshold is met (when the toolchain allows).
- Coverage applies to **statements, branches, and functions** — a single high statement number with untested branches is not sufficient.

## What to test

- **Behavior**: what the user sees and can do (labels, roles, visible text, outcomes of actions).
- **States**: default, loading, empty, error, disabled — when the component supports them.
- **Edge cases**: very long text, zero items, many items, missing optional props.
- Avoid coupling tests to **internal state**, private methods, or implementation-only CSS classes unless the team standard requires it.

## Structure

- **Arrange — Act — Assert** (or Given — When — Then).
- Test names should read like **specifications**: `disables submit when form is invalid`, `shows empty illustration when list has zero items`.
- One concept per assertion block; split unrelated checks into separate test cases.

## Layers

- **Unit**: pure helpers, hooks/composables without heavy UI (when applicable).
- **Component**: render + user events (Testing Library style for React; use the idiomatic approach for Vue/Svelte/Angular per official docs).
- **Integration**: multiple components + data flow; use sparingly for critical user paths.
- **Visual / snapshot** (optional): useful for design-system components when the team adopts it.

## Location

- **Co-locate** tests with source: e.g. `Component.tsx` + `Component.test.tsx` (or `.spec.` per config).
- Respect `test_file_suffix` in `frontend-config.json`.

## Accessibility

- Include at least one check per non-trivial component: correct **role**, **accessible name** (label/aria), or keyboard interaction where relevant.
- Consider automated a11y audit (e.g. `axe-core` integration) for shared/library components.

## Tooling

- Detect **Vitest**, **Jest**, **Playwright**, etc. from `package.json` and follow that stack's official documentation.
- Do not invent custom test APIs; use what the project already configures.
