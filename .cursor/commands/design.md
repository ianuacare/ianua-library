# Design — UX Wireframes, Flows, and Use Cases

Design the user experience: wireframes (ASCII), user flows (Mermaid), use case narratives, UX decision log.

**This command activates the `ux-behaviour` skill.** Load and execute `.cursor/skills/ux-behaviour/SKILL.md`.

The skill follows a facilitator workflow: it surfaces gaps in the related PRD, requires accessibility and responsive notes on every wireframe, and covers all states (default / loading / empty / error / success). It never invents personas or product requirements — it flags gaps to `pm-behaviour`. The final decision is always the user's.

## Suggested next steps after /design

- To implement the wireframe → `/build` (frontend-ts-expert)
- For E2E scenarios derivable from the user flow → `/test` (e2e-tester)
- For SEO-affecting layout choices → `/audit-seo` (seo-expert)

The skill will suggest these handoffs at the end of its workflow.

## Prerequisites

If no PRD exists for the feature, the skill will suggest running `/spec` first.
