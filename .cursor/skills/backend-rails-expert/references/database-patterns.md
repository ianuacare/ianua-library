# Database Patterns — Reference

This file is loaded on demand when the task involves migrations, schema changes, queries, or multi-database configuration.

---

## Multi-Database Architecture

EasyDoctor uses multiple databases in production:

| Database | Purpose | Migration path |
|---|---|---|
| Primary | Application data | `db/migrate/` |
| Queue | Solid Queue jobs | `db/queue_migrate/` |
| Cache | Solid Cache entries | `db/cache_migrate/` |
| Cable | Solid Cable messages | `db/cable_migrate/` |

**Rules:**
- Application migrations always go in `db/migrate/`
- Never modify queue/cache/cable migrations — those are managed by their respective gems
- In test environment, a single database is used

---

## Migrations

### Creating migrations

```bash
bin/rails generate migration AddDepartmentToPathways department:references
bin/rails generate migration CreateVitalSigns patient:references value:decimal unit:string
```

### Writing migrations

```ruby
class AddDepartmentToPathways < ActiveRecord::Migration[8.1]
  def change
    add_reference :pathways, :department, foreign_key: true, index: true
  end
end
```

For non-reversible operations, use explicit `up`/`down`:

```ruby
class MigrateStatusValues < ActiveRecord::Migration[8.1]
  def up
    execute "UPDATE pathways SET status = 1 WHERE status = 'active'"
  end

  def down
    execute "UPDATE pathways SET status = 'active' WHERE status = 1"
  end
end
```

### Rules

1. **One change per migration** — don't combine table creation with data migration
2. **Always reversible** — use `change` with reversible methods, or explicit `up`/`down`
3. **Test rollback** — `bin/rails db:migrate && bin/rails db:rollback` must succeed
4. **Index all foreign keys** — `add_reference` does this by default; verify for manual `add_column`
5. **Add `null: false`** where the column is required — pair with model validation
6. **Use `timestamps`** on every new table
7. **Immutable once merged** — never edit a migration that's been applied; create a new one

---

## Indexes

```ruby
class AddIndexesToPatientSteps < ActiveRecord::Migration[8.1]
  def change
    add_index :patient_steps, [:patient_id, :step_id], unique: true
    add_index :patient_steps, :status
    add_index :user_surveys, [:user_id, :survey_id], unique: true
  end
end
```

**Rules:**
- Index every foreign key column
- Index columns used in `WHERE`, `ORDER BY`, or `GROUP BY` clauses
- Composite indexes for frequent multi-column queries (order matters: most selective first)
- Unique indexes for uniqueness constraints (in addition to model validations)
- Consider partial indexes for queries on a subset of rows

---

## Associations

```ruby
class Pathway < ApplicationRecord
  has_many :steps, -> { where(step_id: nil).order(position: :asc) }, dependent: :destroy
  has_many :pathway_patients, dependent: :destroy, inverse_of: :pathway
  has_many :patients, through: :pathway_patients
end
```

**Rules:**
- Always specify `dependent:` on `has_many` and `has_one` (`:destroy`, `:nullify`, or `:restrict_with_error`)
- Use `inverse_of:` when Rails can't infer it (scoped associations, non-standard naming)
- Use `through:` for many-to-many instead of `has_and_belongs_to_many`
- Default scope on associations: `-> { order(...) }` or `-> { where(...) }`

---

## Preventing N+1 Queries

```ruby
# In controllers
def index
  @pathways = authorized_scope(Pathway.all)
    .includes(:steps, :departments)
    .ransack(params[:q]).result(distinct: true)
  @pagy, @pathways = pagy(@pathways)
end

# In services — preload before iteration
def call
  patient_steps = PatientStep.includes(:step, :patient).where(status: :pending)
  patient_steps.find_each do |ps|
    process(ps)
  end
end
```

**Rules:**
- `includes` — let Rails decide (preload or eager_load)
- `preload` — always separate queries (safe, predictable)
- `eager_load` — LEFT OUTER JOIN (when you need to filter/sort by associated data)
- Use `find_each` for batch processing large result sets (default batch size: 1000)
- Check Rails logs in development for N+1 warnings

---

## Scopes vs Class Methods

```ruby
# Prefer scopes for simple conditions
scope :active, -> { where(status: :active) }
scope :recent, -> { order(created_at: :desc) }

# Use class methods when logic is needed
def self.for_department(department)
  return all if department.blank?
  joins(:departments).where(departments: { id: department })
end
```

**Rules:**
- Scopes always return a relation (even with `nil` — they return `all`)
- Class methods can return `nil` — be careful with chaining
- Both are acceptable; scopes are preferred for readability

---

## Active Record Encryption

```ruby
class User < ApplicationRecord
  encrypts :email, deterministic: true, downcase: true
  encrypts :fiscal_code, deterministic: true
end
```

**Rules:**
- `deterministic: true` — same plaintext always produces same ciphertext; allows `find_by`
- Non-deterministic — more secure but can't query; use for fields only read after fetch
- Configure via env vars (see `ACTIVE_RECORD_ENCRYPTION_*` in `.env.sample`)
- Never add encryption to a field that has existing unencrypted data without a migration strategy

---

## Transactions

```ruby
ActiveRecord::Base.transaction do
  pathway_patient = PathwayPatient.create!(patient:, pathway:)
  pathway.steps.each do |step|
    PatientStep.create!(patient:, step:, pathway_patient:)
  end
end
```

**Rules:**
- Keep transactions short — no I/O (HTTP calls, file operations) inside transactions
- Use `create!` / `update!` (bang methods) inside transactions to trigger rollback on failure
- Use `after_commit` callbacks for side effects that should only run after successful commit
- Beware of deadlocks with concurrent transactions on the same rows
