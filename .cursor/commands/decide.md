# Decide — Record a Decision

Record an architectural, product, UX, or operational decision following the universal pattern. Activates `decision-log-patterns` plus the relevant domain skill.

## How it works

1. **Identify the decision domain** by asking the user (or inferring from context):

   | Domain | Skill | Prefix |
   |---|---|---|
   | Product / scope / prioritization | `pm-behaviour` | `DEC` |
   | UX / interaction / accessibility | `ux-behaviour` | `UXD` |
   | Frontend library / pattern / architecture | `frontend-ts-expert` | `FED` |
   | Backend architecture (TS or Python) | `backend-ts-expert` / `backend-py-expert` | `ADR` |
   | Infrastructure / IaC / cloud | `devops-aws-expert` | `INFRA` |
   | E2E test strategy | `e2e-tester` | `E2ED` |
   | SEO strategy | `seo-expert` | `SEOD` |

2. **Load `.cursor/skills/decision-log-patterns/SKILL.md`** for the universal rules: filename convention, sequential numbering, status lifecycle, Same-PR rule, the 5-section minimum.

3. **Load the domain skill** to access its specific decision template (the one in `templates/<domain>-decision-log-template.md`), which extends the common template with domain-specific extension fields.

4. **Walk the user through the template**:
   - Metadata (Date, Status, Decision maker, Participants)
   - **Context** — what problem, what constraints, what trigger
   - **Options Considered** — at least 2 options with Description / Pros / Cons / domain-specific extensions
   - **Decision** — chosen option, stated unambiguously
   - **Rationale** — why this option, which criteria weighed most
   - Domain-specific extension sections (Trade-offs, Expected Impact, Review Criteria, References)

5. **Save** the decision at `{docs_path}/decisions/{PREFIX}-{NNN}-{slug}.md` with the next sequential number for that prefix.

## Universal rules enforced

- Status starts at `Proposed` and only moves to `Decided` on user confirmation
- Filename matches `{PREFIX}-{NNN}-{slug}.md`
- The 5 base sections (Metadata, Context, Options, Decision, Rationale) are mandatory and cannot be renamed
- At least 2 options must be considered (the "do nothing" baseline counts)
- The decision record must be created in the **same PR** as the change it justifies (Same-PR rule)
- Cross-references to related artifacts use the prefix-and-number convention

## What /decide never does

- **Never** picks the winning option for the user — it presents and asks
- **Never** edits a closed decision — write a new superseding decision instead
- **Never** invents context, options, rationale, or evidence — the user provides them
- **Never** uses real PII in examples
