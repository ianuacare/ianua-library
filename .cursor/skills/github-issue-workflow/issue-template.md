## Context

**Spec**: `specs/features/<feature-name>.md`
**Parent feature**: <!-- Link to parent issue or feature name -->
**Part of**: <!-- e.g., "Step 3 of 8 in Feature X implementation" -->

## Description

<!-- 2-3 sentences describing what this task accomplishes and why it matters. -->

## Acceptance Criteria

- [ ] <!-- Specific, testable criterion 1 -->
- [ ] <!-- Specific, testable criterion 2 -->
- [ ] Tests passing with >80% coverage on new code
- [ ] RuboCop clean (no new offenses)
- [ ] Brakeman clean (no new warnings)

## Technical Notes

**Models affected**: <!-- List model names, e.g., "Step, PatientStep" -->
**Migration needed**: <!-- yes/no — describe changes -->
**New service**: <!-- yes/no — describe responsibility -->
**New policy rule**: <!-- yes/no — describe authorization rule -->
**API endpoint**: <!-- yes/no — OpenAPI spec required if yes -->
**Background job**: <!-- yes/no — recurring or event-driven -->
**Breaking change**: <!-- yes/no -->

## Implementation Order

1. <!-- e.g., "Migration: add position column to steps" -->
2. <!-- e.g., "Model: add validates :position scope" -->
3. <!-- e.g., "Controller: update positions#update action" -->
4. <!-- e.g., "View: add drag handles to step list" -->
5. Tests

## Dependencies

- Blocked by: <!-- #issue-number or "none" -->
- Blocks: <!-- #issue-number or "none" -->

## Definition of Done

- [ ] Code implemented and committed on feature branch
- [ ] All acceptance criteria met
- [ ] PR opened with `Closes #<this-issue>` in body
- [ ] CI passing (audit + lint + tests)
- [ ] Code reviewed
