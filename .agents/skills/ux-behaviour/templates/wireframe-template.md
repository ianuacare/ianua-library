# {WF-NNN} — {Wireframe Title}

| Field | Value |
|-------|-------|
| **Author** | {name} |
| **Date** | {YYYY-MM-DD} |
| **Status** | Draft / In Review / Approved / Superseded |
| **Related PRD** | {PRD-NNN if applicable} |
| **Breakpoint** | {mobile / tablet / desktop / all} |

## Purpose

What screen or interface element does this wireframe represent? What user goal does it serve?

## User Context

- **Who**: {user persona or role}
- **When**: {at what point in the user journey}
- **Goal**: {what the user is trying to accomplish}

## ASCII Wireframe

```
┌─────────────────────────────────────────────┐
│  [Logo]              [Nav Item] [Nav Item]  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │          Hero / Header Area           │  │
│  │       {headline text}                 │  │
│  │       [Primary CTA]                   │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  Card 1  │ │  Card 2  │ │  Card 3  │   │
│  │  {text}  │ │  {text}  │ │  {text}  │   │
│  │  [CTA]   │ │  [CTA]   │ │  [CTA]   │   │
│  └──────────┘ └──────────┘ └──────────┘   │
│                                             │
├─────────────────────────────────────────────┤
│  Footer: [Link] [Link] [Link]              │
└─────────────────────────────────────────────┘
```

### Legend

| Symbol | Meaning |
|--------|---------|
| `[Text]` | Interactive element (button, link) |
| `{text}` | Dynamic / variable content |
| `───`, `│` | Container boundaries |

## Component Inventory

| # | Component | Type | Notes |
|---|-----------|------|-------|
| 1 | {component name} | {button / input / card / nav / ...} | {behavior notes} |
| 2 | {component name} | {type} | {notes} |

## Interaction Notes

- {click / hover / focus behavior}
- {transitions or animations}
- {keyboard navigation}

## States

### Empty State

Describe what the user sees when there is no data to display.

### Error State

Describe what the user sees when an error occurs.

### Loading State

Describe what the user sees while data is being loaded.

## Responsive Notes

| Breakpoint | Adaptation |
|------------|------------|
| Mobile (<768px) | {layout changes, hidden elements, stacking} |
| Tablet (768-1024px) | {adjustments} |
| Desktop (>1024px) | {full layout as shown above} |

## Accessibility Notes

- **Focus order**: {tab sequence through interactive elements}
- **Screen reader**: {alt text, aria labels, landmark roles}
- **Color contrast**: {contrast requirements or notes}
- **Keyboard**: {keyboard-only interaction support}

## References

- Related PRD: {link to PRD-NNN if applicable}
- Related flow: {link to FLOW-NNN if applicable}
- Related use case: {link to UC-NNN if applicable}
- Related UX decision: {link to UXD-NNN if applicable}
- Design assets: {link to mockup/figma if available}
