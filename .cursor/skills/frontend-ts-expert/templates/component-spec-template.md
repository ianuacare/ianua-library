# CMP-NNN — {ComponentName}

## Metadata

| Field | Value |
|--------|--------|
| Status | Draft / In review / Approved |
| Date | YYYY-MM-DD |
| Author | |
| Framework | (e.g. React 19, Vue 3, Svelte 5) |
| Related UX | `WF-NNN-*`, `FLOW-NNN-*` (if any) |
| Related PRD | `PRD-NNN-*` (if any) |

## Purpose

What problem does this component solve? Who uses it?

## Current implementation

- Primary file(s): `path/to/Component.tsx`
- Tests: `path/to/Component.test.tsx`
- README: `path/to/README.md` (if applicable)

## Public API (TypeScript)

```ts
// Props / slots / events — paste or summarize exported types
```

## Reusability checklist

- [ ] Single clear responsibility
- [ ] Props-driven (no hidden global/page coupling)
- [ ] Composable (slots/children/render props as appropriate for the framework)
- [ ] Documented exports (JSDoc + example)

## States & variants

- Default:
- Loading:
- Empty:
- Error:
- Disabled:
- Other variants:

## Responsive behavior

- Breakpoints / layout notes (link to design tokens if any)

## Accessibility

- Roles, labels, keyboard path, focus management
- `prefers-reduced-motion` considerations

## Motion / transitions

- Enter / exit / feedback (or "none")

## Visual notes

- Spacing, typography, color tokens (reference design system)

## Dependencies

- Internal components
- External libraries

## Documentation

- [ ] JSDoc on exports
- [ ] README updated (if component has one)
- [ ] Changelog entry (if change to existing behavior)

## Test plan

| Area | Cases |
|------|--------|
| States | List each state to assert in the DOM |
| Interactions | Clicks, keyboard, form submit, etc. |
| a11y | Role, name, focus |
| Coverage | Target ≥ configured `min_coverage_pct` |

## Open questions

- Items to resolve with design or `ux-behaviour`
