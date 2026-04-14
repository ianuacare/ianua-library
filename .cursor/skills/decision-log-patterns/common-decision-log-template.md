# {PREFIX}-{NNN}: {Decision Title}

| Field | Value |
|---|---|
| **Date** | {YYYY-MM-DD} |
| **Status** | Proposed \| Decided \| Deprecated \| Superseded by {PREFIX}-{NNN} |
| **Decision maker** | {name or role} |
| **Participants** | {comma-separated list of contributors} |

## Context

{What is the problem or opportunity? What constraints exist? What triggered this decision?
Keep it factual and brief — 1 to 3 short paragraphs. Avoid framing the problem as if the
chosen option were already decided.}

## Options Considered

At least two options must be listed. If only one truly viable option exists, list it plus
the "do nothing" baseline and explain why other approaches were dismissed.

### Option A: {short name}

- **Description**: {how it works in one or two sentences}
- **Pros**: {advantages, one bullet each}
- **Cons**: {disadvantages, one bullet each}

### Option B: {short name}

- **Description**: {how it works in one or two sentences}
- **Pros**: {advantages}
- **Cons**: {disadvantages}

<!-- Add Option C, D, … as needed. -->

<!--
  SKILL-SPECIFIC EXTENSION POINT (inside Options):
  Some skills add per-option fields here, such as:
    - "Estimated monthly cost" (devops-aws-expert)
    - "Risk level" (seo-expert)
    - "Complexity" and "Accessibility" (ux-behaviour)
    - "Effort estimate" (pm-behaviour)
  Add them inside each option block, never as a separate top-level section.
-->

## Decision

**Chosen:** Option {X} — {Name}

{One or two sentences restating the decision in active voice.
Do not introduce new options here; the decision must match one of the options above.}

## Rationale

{Why was this option selected? Which criteria weighed most? What trade-offs were
explicitly accepted? Reference any evidence, benchmarks, or prior decisions that
informed the choice.}

<!--
  SKILL-SPECIFIC EXTENSION POINT (after Rationale):
  Add domain-specific sections below this line. Common ones:
    - "## Trade-offs"                       (frontend-ts-expert)
    - "## Expected {Domain} Impact"         (seo-expert, ux-behaviour, pm-behaviour)
    - "## Impact on Test Suite"             (e2e-tester)
    - "## UX Principles Applied"            (ux-behaviour)
    - "## Evidence"                          (pm-behaviour)
    - "## What changes / What risks remain / Follow-up actions"  (devops-aws-expert)
    - "## Review Criteria"                  (pm, ux, seo)
    - "## References"                       (most skills)
  Never reorder or rename the 5 base sections above.
-->

## References

- {Related decisions, e.g. PRD-014, INFRA-024, UXD-007}
- {External documentation links}
- {Implementation PR}
