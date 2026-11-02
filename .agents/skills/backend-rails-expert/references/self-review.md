# Backend Rails — Self-Review Lens

This file is the **self-review lens** for the `backend-rails-expert` skill. It is loaded on demand, not on every invocation. It contains three tools the agent must use before declaring an implementation task "done":

1. **Common Rationalizations** — meta-cognitive patterns that precede a rule violation. If the agent finds itself thinking one of these, it must stop and reconsider.
2. **Red Flags** — observable signals in the diff, in the agent's own behavior, and in the running code. Used to detect violations after they occur.
3. **Ask First decision aids** — concrete examples that disambiguate the most fragile tier of Operating Boundaries.

This file is referenced from the main `SKILL.md` workflow at step 7 (Self-review). The agent must load and apply it before reporting done.

---

## Common Rationalizations

The following are excuses agents (and humans) use to skip steps in this skill. None of them are valid. If you find yourself thinking one of these, stop and follow the skill instead.

| Rationalization | Reality |
|---|---|
| "I'll use ERB here, it's just a quick partial." | Slim is the only template engine in EasyDoctor. ERB creates inconsistency that compounds. The Slim equivalent takes the same effort. |
| "This admin action doesn't need `authorize!`, only admins reach it." | External clinicians are doctors with restricted access. `verify_authorized` will catch the gap in CI, or worse, in production. Always authorize. |
| "I'll add the i18n keys later, let me get the logic working first." | "Later" never comes. Hardcoded strings in templates are immediately visible to users in the wrong locale. Add both `it` and `en` keys now. |
| "I'll add tests after the feature works." | Tests written after the fact confirm the implementation, not the requirements. Write tests alongside the code or immediately after each layer. |
| "Coverage 80% is arbitrary, this service is simple." | Simple code has bugs too. The threshold exists so the agent doesn't get to decide when to skip tests. |
| "I'll skip the migration rollback test, it's straightforward." | "Straightforward" migrations fail during incident response at 3am. Run `db:migrate && db:rollback` locally before declaring done. |
| "This `Time.now` is fine, it's only used in a background job." | Background jobs run in whatever timezone the server is configured for. `Time.zone.now` ensures consistency with the app's `Europe/Rome` timezone. |
| "`permit!` is fine here, I control all the params." | You don't control what a malicious request sends. Explicit strong params are a security boundary, not a convenience choice. |
| "I don't need a policy for this new controller, it's read-only." | Read-only doesn't mean public. External clinicians, patients, and agencies all have different access levels. Authorize every action. |
| "I'll use Kaminari here, Pagy is harder to set up for this case." | Pagy is the project standard. Mixing pagination gems creates confusion and inconsistent UI. Pagy handles every case Kaminari does. |
| "This raw SQL is more readable than the Arel equivalent." | Raw SQL with interpolation is a SQL injection vector. Use `where("col = ?", val)` or Arel. Readability is not worth a security hole. |
| "I'll just `rescue => e; end` here, this error can't really happen." | If it can't happen, the rescue is dead code. If it can happen, you've hidden a bug. Type the error and handle it explicitly or let it propagate. |
| "The form doesn't need `AppFormBuilder`, it's just one field." | Consistency matters more than convenience. `AppFormBuilder` ensures all forms get the same Tailwind styling and accessibility attributes. |

---

## Red Flags

Observable patterns that indicate this skill is being violated. Watch for these during self-review and during code review of work produced under this skill.

### In the diff

- A new `.html.erb` or `.html.haml` file (should be `.html.slim`)
- A controller action without `authorize!` or a `skip_verify_authorized` without justification
- `params.permit!` anywhere
- A hardcoded Italian string in a template, flash message, or mailer subject
- `Time.now` or `Date.today` instead of `Time.zone.now` or `Date.current`
- A new model method or service method without a corresponding test
- `puts`, `pp`, or `print` in production code paths
- A new `has_many` or `belongs_to` without an index on the foreign key
- Business logic inside a controller (more than 3 lines beyond params/authorize/render)
- A `rescue => e; end` block with empty body or only logging
- Raw SQL with string interpolation (`"WHERE id = #{id}"`)
- A migration without `timestamps` on a new table
- A new enum without Ransack allowlist configuration
- `console.log` in a Stimulus controller (should use `console.debug` or remove)

### In the agent's behavior

- The agent says "I'll add tests in a follow-up"
- The agent creates an ERB file "because it's faster"
- The agent skips `authorize!` claiming "only admins use this"
- The agent introduces a gem not in the Gemfile without asking
- The agent skips the Verification checklist
- The agent reports "done" without showing RSpec or RuboCop output
- The agent hardcodes a string saying "it's temporary"
- The agent edits files outside the requested scope without asking
- The agent uses Kaminari, will_paginate, or custom pagination
- The agent writes a service without inheriting `ApplicationService`

### In the running code

- Logs containing user emails, fiscal codes, or health data
- Logs from `puts` or `pp` instead of `Rails.logger`
- N+1 queries visible in development logs (check `bullet` gem if available)
- Flash messages showing raw i18n keys (`translation_missing` errors)
- Turbo Frame responses rendering full layouts instead of frame content
- Authorization errors (403) on actions that should be accessible
- Database queries inside loops without eager loading
- Timezone inconsistencies (dates off by one hour near DST transitions)

---

## Ask First — decision aids

The "Ask First" tier in Operating Boundaries is the most fragile because it requires recognizing a fuzzy boundary. Use the table below to disambiguate. When in real doubt, default to asking — false positives cost a question, false negatives cost trust.

### Disambiguation table

| Situation | Ask First? | Why |
|---|---|---|
| Adding a gem that's already in the Gemfile (e.g. another Devise module) | **No** | The dependency already exists; you're using more of it |
| Adding a completely new gem not in the Gemfile | **Yes** | New dependency; maintenance, size, and compatibility need evaluation |
| Adding a new column to an existing table | **Yes** | Schema change; requires migration review |
| Adding a new column to a table in an unapplied migration (still in development) | **No** | Same migration, still in design |
| Adding a new index to an existing table | **Yes** | Schema change; index creation can lock tables in production |
| Adding a new model with migration | **Yes** | Schema change; new domain concept requires agreement |
| Adding a new scope to an existing model | **No** | In-scope query encapsulation, no schema change |
| Adding a new concern shared by 2+ models | **No** | Standard Rails pattern for code reuse |
| Adding a new service in an existing namespace (e.g. `Surveys::NewService`) | **No** | Follows existing patterns, no architectural change |
| Adding a new controller namespace (e.g. `Backoffice::Reports::`) | **Yes** | New routing namespace; URL and authorization impact |
| Adding a new action to an existing controller | **No** | Within existing resource, if routed consistently |
| Modifying an existing policy's rules | **Yes** | Authorization changes affect access control |
| Adding a new policy for a new controller | **No** | Required by convention; mirrors the controller |
| Adding a new recurring job to `config/recurring.yml` | **Yes** | Recurring jobs consume resources on a schedule |
| Adding a one-off background job class | **No** | Standard pattern for async work |
| Switching from `turbo_frame` to `turbo_stream` for an existing feature | **Yes** | Changes the interaction model; user should confirm UX |
| Adding a new Stimulus controller for a new feature | **No** | Standard frontend pattern within the existing stack |
| Modifying Devise configuration (timeout, password rules, etc.) | **Yes** | Authentication changes are high-impact |
| Adding Active Record Encryption to a field | **Yes** | Changes how data is stored; may affect existing queries |
| Renaming a route or URL helper used across the app | **Yes** | Broad blast radius; touches every reference |
| Adding a new locale key in both `it.yml` and `en.yml` | **No** | Required by convention; always do both |
| Modifying an existing locale key's text | **Yes** | Affects user-visible content; stakeholder decision |
| Adding a new mailer or email template | **No** | Standard Rails pattern, if the feature requires it |
| Changing the email content of an existing mailer | **Yes** | Affects user-visible communication |

### Default rule

If the change is **inside the file or module being actively edited** AND covered by an "Always Do" rule, proceed. Otherwise, when in doubt, ask.
