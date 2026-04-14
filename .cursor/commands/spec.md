# Spec — Define Product Requirements

Start a structured product specification: PRD, user stories, acceptance criteria, prioritization, decision log.

**This command activates the `pm-behaviour` skill.** Load and execute `.cursor/skills/pm-behaviour/SKILL.md`.

The skill follows a facilitator workflow: it asks clarifying questions, applies the configured prioritization framework (RICE / MoSCoW / Impact-Effort), uses the registered template, and produces artifacts under `docs/specs/product/`. The final decision is always the user's.

## Suggested next steps after /spec

- For user-facing features → `/design` (ux-behaviour)
- To track implementation → use `pm-github-workflow` (suggest, never auto-invoke)
- For E2E scenarios derivable from acceptance criteria → `/test` (e2e-tester)

The skill will suggest these handoffs at the end of its workflow.
