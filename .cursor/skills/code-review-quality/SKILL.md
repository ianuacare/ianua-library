---
name: code-review-quality
description: >-
  Review implemented code for quality, readability, maintainability, performance,
  and security following EasyDoctor standards. Use when reviewing a pull request,
  performing a refactoring pass, doing a code quality audit, or when asked to
  improve code quality, identify technical debt, or optimize existing code.
---

# Code Review & Quality

Systematic review producing actionable, prioritized feedback.

## Review Checklist

Run through each category. For each finding, note severity and location.

### Readability
- [ ] Method names express intent (verb + noun for actions)
- [ ] No method longer than 15 lines — extract if longer
- [ ] No class longer than 200 lines — split by responsibility
- [ ] No deeply nested conditionals (max 2 levels) — use guard clauses
- [ ] Complex logic has a comment explaining *why*, not *what*
- [ ] No "magic numbers" — extract to named constants or enums

### Maintainability
- [ ] Single Responsibility: one reason to change per class/method
- [ ] DRY: no duplicated business logic (but don't over-abstract)
- [ ] Follows project patterns: services for business logic, policies for auth, components for UI
- [ ] No logic in controllers beyond parameter handling and rendering
- [ ] No raw SQL strings — use ActiveRecord scopes or Arel
- [ ] Correct namespace: backoffice logic in `Backoffice::`, etc.

### Testability
- [ ] Dependencies are injectable (not hardcoded inside methods)
- [ ] Side effects isolated in service objects
- [ ] No `Time.now` — use `Time.zone.now` (testable with travel_to)
- [ ] No `rand` without seed — use deterministic alternatives in tests
- [ ] Coverage >80% on new code (`COVERAGE=true bin/rspec`)

### Performance
- [ ] No N+1 queries — use `includes`, `preload`, or `eager_load`
- [ ] New DB queries on associated records use proper indexes
- [ ] Bulk operations use `insert_all`/`update_all` where appropriate
- [ ] Expensive operations (file processing, external API calls) in background jobs
- [ ] No synchronous HTTP calls in controller actions

### Security (Healthcare Critical)
- [ ] No PII in logs — no `logger.info user.email` etc.
- [ ] Strong parameters enforced — no `permit!`
- [ ] `authorize!` called in every controller action (or `verify_authorized` covers it)
- [ ] No user-controlled SQL fragments
- [ ] No `send()` or `eval()` with user input
- [ ] Sensitive attributes encrypted with Active Record Encryption
- [ ] Webhook signatures verified before processing

### EasyDoctor-Specific
- [ ] Slim templates used (not ERB)
- [ ] Translations via `t()` helper (no hardcoded Italian)
- [ ] Pagination via Pagy (not custom or other gems)
- [ ] Forms use `AppFormBuilder`
- [ ] API responses are JSON with proper status codes

## Severity Levels

Use these prefixes when reporting findings:

| Severity | Label | Meaning |
|----------|-------|---------|
| Must fix | `[CRITICAL]` | Bug, security issue, or broken functionality — blocks merge |
| Should fix | `[MAJOR]` | Significant quality issue — fix before or shortly after merge |
| Consider | `[MINOR]` | Improvement opportunity — nice to have |
| Note | `[NOTE]` | Observation for future reference, no action required |

## Output Format

For each finding:
```
[SEVERITY] file.rb:line_number
Issue: what is wrong and why it matters
Fix: concrete code suggestion
```

Example:
```
[CRITICAL] app/controllers/backoffice/patients_controller.rb:23
Issue: Missing `authorize!` call — any authenticated user can access this action
Fix: Add `authorize! @patient, with: Backoffice::PatientPolicy` after line 22

[MAJOR] app/services/surveys/check_automatic_assignments.rb:45
Issue: N+1 query — `user.surveys` called inside a loop
Fix: Preload surveys before the loop:
  users = User.includes(:surveys).where(...)

[MINOR] app/models/patient_step.rb:78
Issue: Method is 18 lines — exceeds 15-line guideline
Fix: Extract the email-sending logic into a separate private method `#notify_completion`
```

## Additional Standards

See [standards.md](standards.md) for detailed metrics and thresholds.
