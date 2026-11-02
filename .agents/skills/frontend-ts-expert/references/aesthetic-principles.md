# Aesthetic principles (frontend UI)

Use these as defaults when the project has no design system. Prefer project tokens and UX specs when they exist.

> **Project design system takes precedence.** When the project configures `design_tokens_path`, `components_path`, or `style_guide_path`, defer to those project-specific tokens, components, and patterns over the generic guidelines below. These principles serve as fallback defaults.

## Spacing

- Use a **consistent rhythm**: 4px base unit (4, 8, 12, 16, 24, 32, 48, 64). Avoid arbitrary values that break the grid.
- **Whitespace is hierarchy**: more space around primary actions and section boundaries; group related controls tightly (8–12px); separate sections generously (24–48px).
- Touch targets: minimum 44×44 CSS px for interactive elements (WCAG 2.5.8).

## Typography

- Establish a **modular scale** (e.g. ratio ~1.25: 12 → 14 → 16 → 20 → 24 → 32). Limit to 3–4 distinct sizes per view.
- Use **font-weight contrast** (400 body / 600 emphasis / 700 headings) before adding a size.
- Line-height: ~1.5 for body text; ~1.2 for headings. Tighten display text only when the design system allows.
- Pair fonts deliberately: one for headings, one for body; avoid mixing more than two families.

## Color

- Use color **semantically**: primary (brand action), destructive, success, warning, neutral, muted.
- Meet **WCAG AA contrast** minimum: 4.5:1 for normal text, 3:1 for large text and UI components.
- Plan **light and dark** variants from the start; use CSS custom properties or tokens — no hardcoded hex values scattered in code.
- Avoid conveying meaning by color alone (pair with icon, text, or shape).

## Motion

- Motion should **communicate**: entrance orients, exit dismisses, feedback confirms.
- **Duration guidance**: micro-interactions 100–200ms; panel/modal transitions 200–350ms; page-level transitions 300–500ms. Ease-out for entrances; ease-in for exits.
- Do not animate layout properties (width/height) when `transform` or `opacity` can achieve the same effect — prefer GPU-friendly properties.
- Respect **`prefers-reduced-motion: reduce`**: collapse durations to 0 or near-0, or replace motion with an instant state change.

## Layout

- **Content-first responsive**: start from the smallest breakpoint, then enhance (mobile-first CSS).
- Prefer flexible layouts (`grid` / `flexbox`) over fixed pixel widths for structural elements.
- Common breakpoint tokens: sm ~640px, md ~768px, lg ~1024px, xl ~1280px — adapt to the project's system.
- Be aware of **container queries** when the project stack supports them; use for component-scoped responsiveness.

## Polish

- Every interactive element must have visible **hover, focus, active, disabled** states (as applicable).
- Implement **loading** (skeleton matching final layout), **empty** (guiding message + action), and **error** (clear message + retry) states; never leave a silent blank screen.
- **Focus visibility** is mandatory; `:focus-visible` outline or ring — do not remove outlines without an accessible replacement.
- Skeletons and placeholders should match content dimensions to minimize layout shift (CLS).
- Prefer subtle **box-shadow** depth over hard borders when the design system allows.

## Anti-patterns

- Default browser styling everywhere with no visual hierarchy.
- Animations > 500ms on interactive controls, or looping animations without user control.
- Tiny click targets (< 44px) and missing keyboard support.
- Copy-pasted spacing values with no underlying system.
- Hardcoded colors outside the token palette.
