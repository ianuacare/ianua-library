# Code Quality Standards Reference

Concrete thresholds and metrics for the code-review-quality skill.

## Size Limits

| Unit | Max Lines | Action if exceeded |
|------|-----------|-------------------|
| Method | 15 | Extract to private methods |
| Class | 200 | Split by responsibility (SRP) |
| Controller action | 10 | Move logic to service object |
| Migration | — | One concern per migration file |
| Spec example (`it` block) | 20 | Split into multiple examples |

## Complexity

- **Cyclomatic complexity**: max 5 per method (RuboCop `Metrics/CyclomaticComplexity`)
- **Nested conditionals**: max 2 levels deep
- **Method arguments**: max 5 (use keyword args or value objects)

## Test Coverage

| Scope | Minimum |
|-------|---------|
| Overall project | 80% |
| Per file | 70% |
| New code in PR | 80% |
| Critical paths (auth, payments) | 95% |

## Database

### Query Rules
- Always use `includes`/`preload` when iterating associations
- Avoid `select *` in scopes — specify columns
- Use `find_each` for large dataset iteration (not `all.each`)
- Use `insert_all`/`upsert_all` for bulk inserts (not `each { create }`)

### Index Requirements
- Foreign keys must have indexes
- Columns used in `where`, `order`, or `group` must have indexes
- Composite indexes: order matters (most selective column first)

## Rails Conventions

### Controllers
```ruby
# Good: thin controller
def create
  @pathway = authorize!(Pathway.new(pathway_params))
  if @pathway.save
    redirect_to [:backoffice, @pathway], notice: notice
  else
    render :new, status: :unprocessable_entity
  end
end

# Bad: fat controller
def create
  @pathway = Pathway.new(pathway_params)
  @pathway.steps.build  # business logic in controller
  if @pathway.valid? && some_complex_check(@pathway)  # business logic
    @pathway.save
    # ... 20 more lines
  end
end
```

### Services
```ruby
# Good: single responsibility, clear interface
class Surveys::CheckAutomaticAssignments < ApplicationService
  param :user

  def call
    eligible_surveys.each { |survey| assign_to_user(survey) }
  end

  private

  def eligible_surveys
    Survey.automatic.where(...)
  end

  def assign_to_user(survey)
    UserSurvey.find_or_create_by!(user:, survey:)
  end
end
```

### Models
```ruby
# Good: validation + scope + no business logic
class PatientStep < ApplicationRecord
  belongs_to :patient
  belongs_to :step
  belongs_to :pathway_patient

  validates :status, presence: true

  scope :pending, -> { where(status: :pending) }
  scope :completed, -> { where(status: :completed) }

  # OK: simple derived value
  def overdue?
    due_at.present? && due_at < Time.zone.now && pending?
  end
end

# Bad: business logic in model
def send_reminder_email!
  PatientStepMailer.reminder(self).deliver_later  # side effect in model
  update!(reminder_sent_at: Time.zone.now)
end
# → Move to a service: Backoffice::PatientSteps::ProcessEmail
```

## Security Thresholds

| Risk | Threshold | Action |
|------|-----------|--------|
| Brakeman warnings | 0 (w2) | Block merge |
| bundler-audit CVEs | 0 | Block merge |
| importmap CVEs | 0 | Block merge |
| Unencrypted PII fields | 0 | Immediate fix |
| Missing authorization | 0 | Block merge |
