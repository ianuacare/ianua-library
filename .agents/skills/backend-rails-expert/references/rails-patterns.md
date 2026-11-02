# Rails Patterns — Reference

This file is loaded on demand when the task involves Ruby/Rails idioms. It documents the patterns used in the EasyDoctor codebase.

---

## Concerns

Concerns extract shared behavior across models or controllers.

```ruby
# app/models/concerns/departmentable.rb
module Departmentable
  extend ActiveSupport::Concern

  included do
    has_many :department_assignments, as: :departmentable, dependent: :destroy
    has_many :departments, through: :department_assignments
  end

  def department_ids=(ids)
    # custom setter logic
  end
end
```

**Rules:**
- Place in `app/models/concerns/` or `app/controllers/concerns/`
- Use `extend ActiveSupport::Concern` with `included` block for associations/callbacks
- A concern should encapsulate one cohesive behavior
- Prefer concerns over multiple inheritance or mixins from `lib/`

---

## Single Table Inheritance (STI)

EasyDoctor uses STI for the `User` model:

```ruby
class User < ApplicationRecord
  # Base class — shared auth, validations, associations
  def admin? = is_a?(Admin)
  def doctor? = is_a?(Doctor)
  def patient? = is_a?(Patient)
  def agency? = is_a?(Agency)
end

class Admin < User
  def god? = super_admin
end

class Doctor < User
  def external_clinician? = external
end

class Patient < User
  has_one :patient_info, dependent: :destroy
end
```

**Rules:**
- The `type` column is managed by Rails — never set it manually
- Use `is_a?` for type checks, never `type == "Admin"`
- Add type-specific associations only in the subclass
- Factory definitions: `factory :admin, class: "Admin", parent: :user`

---

## Scopes

Prefer scopes for reusable query conditions:

```ruby
class Pathway < ApplicationRecord
  scope :active, -> { where(status: :active) }
  scope :for_department, ->(dept) { joins(:departments).where(departments: { id: dept }) }
  scope :recent, -> { order(created_at: :desc) }
end
```

**Rules:**
- Scopes return `ActiveRecord::Relation` (chainable)
- Name scopes as adjectives or prepositions (`active`, `for_department`, `with_steps`)
- Complex queries with branching logic: use class methods returning relations
- Never use `default_scope` — it causes subtle bugs and is hard to override

---

## Enums

```ruby
class Pathway < ApplicationRecord
  enum :status, %i[pending active].index_with(&:to_s)
end

class User < ApplicationRecord
  enum :locale, I18n.available_locales
  enum :two_factors, { enabled: 0, disabled: 1 }, prefix: true
end
```

**Rules:**
- Use `enum :name, { ... }` syntax (Rails 7+ keyword style)
- Use `prefix: true` when the enum name could clash with methods from other enums
- For Ransack: add enum to `ransackable_attributes` and use `ransack-enum` gem
- Always back with integer columns in the database

---

## Callbacks

Use sparingly. Prefer service objects for complex side effects.

```ruby
class PatientStep < ApplicationRecord
  after_update :schedule_email, if: :saved_change_to_status?

  private

  def schedule_email
    PatientStepEmailsJob.perform_later(id) if completed?
  end
end
```

**Rules:**
- Acceptable: simple state transitions, cache invalidation, counter updates
- Avoid: external API calls, complex business logic, anything that can fail silently
- Prefer `after_commit` over `after_save` when triggering background jobs (ensures transaction committed)
- Never use callbacks for authorization logic

---

## Validations

```ruby
class User < ApplicationRecord
  validates :first_name, presence: true
  validates :email, uniqueness: { scope: nil }  # global uniqueness with encryption
  validates :fiscal_code, format: { with: /\A[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\z/ }, allow_blank: true
end
```

**Rules:**
- Model validations for data integrity (presence, uniqueness, format)
- Controller-level validation only for params that don't map to model attributes
- Use custom validators in `app/validators/` for complex reusable validation logic
- Always add database-level constraints (NOT NULL, UNIQUE indexes) alongside model validations

---

## Encrypted Attributes

```ruby
class User < ApplicationRecord
  encrypts :email, deterministic: true, downcase: true
end
```

**Rules:**
- Use `deterministic: true` when you need to query by the field (e.g. `find_by(email:)`)
- Use non-deterministic encryption for fields that are never queried directly
- Configure keys via environment variables: `ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY`, `ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY`, `ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT`
- Never log encrypted field values — they should remain opaque

---

## Ransack Search

```ruby
class Pathway < ApplicationRecord
  def self.ransackable_attributes(auth_object = nil)
    %w[name status created_at]
  end

  def self.ransackable_associations(auth_object = nil)
    %w[departments]
  end
end
```

In controllers:

```ruby
def index
  authorize! Pathway
  @q = authorized_scope(Pathway.all).ransack(params[:q])
  @pagy, @pathways = pagy(@q.result(distinct: true))
end
```

**Rules:**
- Always define `ransackable_attributes` and `ransackable_associations` allowlists
- Use `ransack-enum` for filtering by enum fields
- Combine with `authorized_scope` for authorization-aware search
- Never pass unfiltered `params[:q]` without Ransack allowlists

---

## Clowne (Record Cloning)

```ruby
class PathwayCloner < Clowne::Cloner
  adapter :active_record

  include_association :steps, clone_with: StepCloner
  nullify :status

  after_persist do |_source, record|
    record.update!(name: "#{record.name} (copy)")
  end
end

# Usage
PathwayCloner.call(pathway)
```

**Rules:**
- Cloners live alongside models or in `app/cloners/`
- Use `include_association` with nested cloners for deep-copy
- Use `nullify` for fields that should reset (status, published_at, etc.)
- Test cloning thoroughly — association integrity is critical

---

## Positioning Gem

For ordered collections:

```ruby
class Step < ApplicationRecord
  positioned on: :pathway  # scoped positioning within a pathway
end
```

**Rules:**
- Use the `positioning` gem instead of manual position management
- Always scope positioning to the parent (`on: :parent_association`)
- The gem handles reordering automatically on create/destroy
