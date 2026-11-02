# Service Patterns — Reference

This file is loaded on demand when the task involves service objects, query objects, or the ApplicationService pattern.

---

## ApplicationService Base

```ruby
# app/services/application_service.rb
class ApplicationService
  extend Dry::Initializer

  def self.call(**)
    new(**).call
  end

  def call
    raise "Implement me"
  end
end
```

**Key points:**
- `Dry::Initializer` provides `option` (keyword arguments) and `param` (positional arguments)
- EasyDoctor convention: **always use `option`** (keyword style), never `param`
- Invocation: `ServiceClass.call(key: value)` — the class method instantiates and calls `#call`
- Every service must implement `#call`

---

## Writing a Service

```ruby
# app/services/surveys/check_automatic_assignments.rb
module Surveys
  class CheckAutomaticAssignments < ::ApplicationService
    option :user

    def call
      AssignAutomaticSurveysToUserQuery.call(user:)
    end
  end
end
```

### Conventions

1. **Namespace by domain**: `Surveys::`, `Backoffice::PatientSteps::`, `Formulas::`
2. **One public method**: `#call` — if you need multiple entry points, you need multiple services
3. **Options via `option`**: declare dependencies as keyword options
4. **File location**: `app/services/<namespace>/<service_name>.rb`
5. **Naming**: verb + noun or descriptive action (e.g. `ProcessEmail`, `CheckAutomaticAssignments`, `BmiCalculator`)

### Example with private helpers

```ruby
module Backoffice
  module PatientSteps
    class ProcessEmail < ::ApplicationService
      option :patient_step

      def call
        return unless patient_step.scheduled?

        notify
        update!
      end

      private

      def notify
        PatientStepMailer.step_email(patient_step).deliver_later
      end

      def update!
        patient_step.update!(status: :notified, notified_at: Time.zone.now)
      end
    end
  end
end
```

---

## Option Types and Defaults

```ruby
class MyService < ApplicationService
  option :user                                    # required keyword
  option :notify, default: -> { true }            # optional with default
  option :logger, default: -> { Rails.logger }    # injectable dependency
end
```

**Rules:**
- Required options: declare without default — will raise `KeyError` if missing
- Optional options: use `default: -> { value }` (must be a proc/lambda)
- Injectable dependencies: provide sensible defaults, allow override for testing

---

## Query Objects

For complex queries reused across services:

```ruby
# app/queries/assign_automatic_surveys_to_user_query.rb
class AssignAutomaticSurveysToUserQuery
  def self.call(user:)
    new(user:).call
  end

  def initialize(user:)
    @user = user
  end

  def call
    Survey.automatic.where.not(id: @user.surveys.select(:id)).find_each do |survey|
      @user.user_surveys.create!(survey:)
    end
  end
end
```

**Rules:**
- Query objects encapsulate complex database queries
- Place in `app/queries/` (or follow existing project convention)
- Same `.call` interface as services for consistency
- Return `ActiveRecord::Relation` when possible for chainability

---

## Error Handling in Services

```ruby
class Payments::ProcessRefund < ApplicationService
  option :payment

  def call
    validate!
    execute_refund
    notify_patient
  end

  private

  def validate!
    raise ActiveRecord::RecordNotFound, "Payment not found" unless payment
    raise ArgumentError, "Payment already refunded" if payment.refunded?
  end
end
```

**Guidelines:**
- Raise specific errors — `ActiveRecord::RecordNotFound`, `ArgumentError`, custom error classes
- Let errors propagate to the controller for appropriate HTTP response
- For operations that can partially succeed, consider returning a result struct
- Never rescue and silently swallow errors inside a service

---

## Testing Services

```ruby
RSpec.describe Surveys::CheckAutomaticAssignments do
  describe ".call" do
    let(:user) { create(:patient) }
    let!(:automatic_survey) { create(:survey, automatic: true) }

    it "assigns automatic surveys to the user" do
      expect {
        described_class.call(user:)
      }.to change { user.user_surveys.count }.by(1)
    end

    it "does not assign already-assigned surveys" do
      create(:user_survey, user:, survey: automatic_survey)

      expect {
        described_class.call(user:)
      }.not_to change { user.user_surveys.count }
    end
  end
end
```

**Testing rules:**
- Test via `.call` (the public interface), not `#call` on an instance
- Test happy path, edge cases (empty input, already-exists), and error scenarios
- Use FactoryBot for test data
- Mock external dependencies, never internal service logic
