---
name: decision-log-patterns
description: >-
  Defines the universal pattern for decision records (ADRs) across all skills in this scaffold:
  filename convention, sequential numbering, status lifecycle, the Same-PR rule, the common ADR
  template, and the cross-reference matrix between artifact prefixes (PRD, DEC, UXD, FED, INFRA,
  E2ED, SEOD, etc.). Activates implicitly whenever another skill is about to create a decision
  record, and explicitly when the user asks how decisions are tracked, what the prefixes mean,
  how to add a new prefix, or how to cross-reference between artifacts. This skill does NOT
  produce decisions itself — it is the standard that other skills follow.
---

# Decision Log Patterns — Transversal Standard

## When to Activate

### Activate this skill when:

- Another skill is about to write a decision record (ADR, decision log entry, design decision)
- The user asks "how do we track decisions in this project?"
- The user asks what a prefix means (UXD, FED, INFRA, etc.) or how prefixes relate
- A new skill is being created and needs its own decision log prefix
- The user asks how to cross-reference an artifact from one skill in another
- An existing decision is being superseded and needs lifecycle handling

### Do NOT activate for:

- Producing the decision content itself — that is the originating skill's job (pm-behaviour for product decisions, ux-behaviour for UX, etc.)
- General documentation tasks unrelated to decisions (READMEs, API docs, runbooks)
- Code review or implementation work

## Role: Transversal Standard

This skill is **not an execution skill and not a facilitator**. It is the **scaffold-level standard** that every other skill must follow when producing decision records. Think of it as the typography of the design system: every component uses it, no component owns it.

It exists for one reason: **a single source of truth for the ADR format prevents 8 copies from drifting apart**. When the format evolves, it evolves here.

## Universal Rules

These rules apply to **every** decision record produced by **any** skill in this scaffold. No exceptions.

### Filename convention

Every decision record is a single Markdown file named:

```
{PREFIX}-{NNN}-{slug}.md
```

Where:

- `PREFIX` is the skill's registered prefix (see Prefix Registry below). Always uppercase letters.
- `NNN` is a 3-digit zero-padded sequential number, scoped per prefix. The next number is determined by listing existing files in the same `decisions/` directory and adding 1.
- `slug` is a lowercase, kebab-case short identifier (3–6 words) describing the decision.

Examples: `UXD-007-onboarding-progress-bar.md`, `INFRA-024-multi-az-rds.md`, `FED-012-state-management-zustand.md`.

### Output location

Every decision record is stored at:

```
{docs_path}/decisions/{PREFIX}-{NNN}-{slug}.md
```

Where `{docs_path}` is the per-skill docs path (defined in the originating skill's config — usually `docs/specs/{domain}/`).

### Sequential numbering

- Numbers are scoped per prefix, not globally. UXD-007 and FED-007 are independent.
- Numbers are never reused, even after a decision is deprecated or superseded.
- Before creating a new record, list the existing files in the target `decisions/` directory and pick the next available number.
- Do not leave gaps. If you find one, do not fill it; just continue from the highest number.

### Status lifecycle

Every decision record has a `Status` field with one of these values:

| Status | Meaning |
|---|---|
| **Proposed** | Drafted but not yet decided. Open for review. |
| **Decided** | The decision is in effect. This is the steady state. |
| **Deprecated** | No longer the right choice but no replacement exists yet. Code may still rely on it. |
| **Superseded by {PREFIX}-{NNN}** | Replaced by another decision. Always link to the successor. |

Transitions are forward-only: Proposed → Decided → (Deprecated | Superseded). A Decided record is never edited to change the decision — instead, write a new record that supersedes it.

### Same-PR rule

A decision record must be created **in the same pull request** as the change it justifies. This is non-negotiable.

- A code change that introduces a new architectural pattern → create the ADR in the same PR.
- A schema migration → create the INFRA or backend ADR in the same PR.
- A UX redesign → create the UXD in the same PR as the wireframe/flow update.

A PR that introduces a decision-worthy change without its decision record is **incomplete** and must be blocked in review.

### The 5-section minimum

Every decision record, regardless of skill, contains at least these 5 sections in this order:

1. **Metadata header** (Date, Status, Decision maker, Participants)
2. **Context** — what problem, what constraints, what trigger
3. **Options Considered** — at least 2 options, each with Description / Pros / Cons
4. **Decision** — which option, stated unambiguously
5. **Rationale** — why this option, which criteria weighed most

Skills may add domain-specific sections after Rationale (see Extension Points). They may **not** remove or rename any of the 5 base sections.

## The Common Template

The base ADR template lives at `common-decision-log-template.md` in this skill directory. Every skill-specific template in the scaffold (e.g. `ux-behaviour/templates/ux-decision-log-template.md`) is a **superset** of this base: it contains the same 5 base sections (named identically) plus its own extension sections.

When in doubt, copy the common template and add domain-specific sections after Rationale.

## Prefix Registry

Every skill that produces decision records owns exactly one prefix. New skills must register their prefix here before being added to the scaffold.

| Prefix | Owning skill | Domain | Output path |
|---|---|---|---|
| `DEC` | `pm-behaviour` | Product decisions | `docs/specs/product/decisions/` |
| `UXD` | `ux-behaviour` | UX design decisions | `docs/specs/ux/decisions/` |
| `FED` | `frontend-ts-expert` | Frontend/library/architecture decisions | `docs/specs/frontend/decisions/` |
| `INFRA` | `devops-aws-expert` | Infrastructure and IaC decisions | `docs/specs/devops/decisions/` |
| `E2ED` | `e2e-tester` | E2E testing strategy decisions | `docs/specs/e2e/decisions/` |
| `SEOD` | `seo-expert` | SEO strategy decisions | `docs/specs/seo/decisions/` |
| `ADR` | `backend-ts-expert` / `backend-py-expert` | Backend architectural decisions | `docs/specs/backend/decisions/` |

### Reserved prefixes (do not use for decision logs)

These prefixes are used for **non-decision artifacts** and must not be reused for decision records:

| Prefix | Owning skill | Artifact type |
|---|---|---|
| `PRD` | `pm-behaviour` | Product Requirement Documents |
| `WF` | `ux-behaviour` | Wireframes |
| `FLOW` | `ux-behaviour` | User flows |
| `UC` | `ux-behaviour` | Use cases |
| `CMP` | `frontend-ts-expert` | Component specs |
| `PAGE` | `frontend-ts-expert` | Page specs |
| `E2E` | `e2e-tester` | E2E scenarios |
| `SUITE` | `e2e-tester` | E2E suites |
| `SEO` | `seo-expert` | SEO audits |
| `SEOS` | `seo-expert` | SEO strategies |

### Adding a new prefix

When a new skill is added to the scaffold and needs decision records:

1. Pick a prefix that is unique across both tables above (decision and reserved).
2. Prefer 3–5 uppercase letters. Shorter is better.
3. Update both tables in this file in the same PR that adds the new skill.
4. Do not reuse a deprecated prefix; pick a new one.

## Cross-Reference Patterns

Decision records often reference artifacts from other skills (and other decisions). Use these conventions to keep references machine-traversable.

### How to reference

Inside a decision record, reference other artifacts inline by their prefix and number, optionally with a relative link:

```markdown
This decision implements [PRD-014](../../product/PRD-014-onboarding-redesign.md)
and supersedes [UXD-006](./UXD-006-old-progress-pattern.md).
Related infrastructure change: [INFRA-024](../../devops/decisions/INFRA-024-multi-az-rds.md).
```

### Standard cross-reference matrix

Skills that **typically** reference each other's artifacts:

| Skill | Commonly references |
|---|---|
| `e2e-tester` | `PRD-NNN` (acceptance criteria), `FLOW-NNN`, `UC-NNN`, `WF-NNN`, `CMP-NNN`, `PAGE-NNN` |
| `frontend-ts-expert` | `WF-NNN`, `FLOW-NNN`, `PRD-NNN`, `UXD-NNN` |
| `ux-behaviour` | `PRD-NNN`, `DEC-NNN` (product), `CMP-NNN`, `PAGE-NNN` |
| `pm-behaviour` | Other `DEC-NNN`, evidence sources |
| `devops-aws-expert` | Other `INFRA-NNN`, implementation PR |
| `seo-expert` | `PRD-NNN`, `WF-NNN`, `FLOW-NNN`, Google Search Central docs |
| `backend-ts-expert` / `backend-py-expert` | Other backend ADRs, OpenAPI spec, schema docs |

### "References" section

Most skill-specific templates include a `## References` section near the end. Use it to list related artifacts as a flat bullet list. This section is optional in the common template, mandatory in 4 of 6 skill templates today.

## Extension Points (for skill authors)

When designing a new skill-specific decision template, **start from `common-decision-log-template.md`** and add sections **after Rationale**, never before. Common extension sections used today:

| Extension section | Used by |
|---|---|
| `## Trade-offs` | `frontend-ts-expert` |
| `## Estimated monthly cost` (inside Options) | `devops-aws-expert` |
| `## Risk level` (inside Options) | `seo-expert` |
| `## Complexity` and `## Accessibility` (inside Options) | `ux-behaviour` |
| `## Effort estimate` (inside Options) | `pm-behaviour` |
| `## Evidence` | `pm-behaviour` |
| `## Expected {Domain} Impact` | `seo-expert`, `ux-behaviour`, `pm-behaviour` |
| `## Impact on Test Suite` | `e2e-tester` |
| `## UX Principles Applied` | `ux-behaviour` |
| `## What changes / What risks remain / Follow-up actions` | `devops-aws-expert` |
| `## Review Criteria` (When to review, Success criteria, How to measure) | `pm-behaviour`, `seo-expert`, `ux-behaviour` |
| `## References` | most skills |

When adding a new section, prefer reusing one of the names above to keep cross-skill consistency. Invent a new section name only when no existing one fits.

## Verification

This skill has no execution workflow of its own. The verification it enforces on **other** skills:

- [ ] Filename matches `{PREFIX}-{NNN}-{slug}.md`
- [ ] File is in the correct `decisions/` directory for the prefix
- [ ] The 5 base sections are present and named identically to the common template
- [ ] Status is one of: Proposed, Decided, Deprecated, Superseded by …
- [ ] If Status is "Superseded by", the successor link is present and resolves
- [ ] At least 2 options were considered
- [ ] The decision record was created in the same PR as the change it justifies
- [ ] Cross-references to other artifacts use the prefix-and-number convention
- [ ] If a new prefix was introduced, the Prefix Registry above was updated in the same PR

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's a small decision, I'll skip the ADR." | Small decisions accumulate and become invisible institutional knowledge. The ADR takes 5 minutes; future-you will thank you. |
| "I'll write the decision record after the PR is merged." | "After" never comes. Decisions are most accurately captured in the moment they are made, not reconstructed later. |
| "Only one option made sense, I don't need an Options Considered section." | If only one option made sense, write it down anyway and explicitly say why others were dismissed. The "considered and rejected" record is often more valuable than the chosen option. |
| "I'll edit the existing ADR instead of writing a superseding one." | Editing destroys history. Future readers need to see what changed and why. Write a new ADR and mark the old one Superseded. |
| "I don't need to update the Prefix Registry, my prefix is obvious." | Without the registry, two skills will eventually pick the same prefix and the cross-reference system breaks. |

## Bundled Resources

```
decision-log-patterns/
├── SKILL.md
├── common-decision-log-template.md      # the 5-section base template
└── decision-log-config.example.json     # example config (currently unused, reserved for future)
```
