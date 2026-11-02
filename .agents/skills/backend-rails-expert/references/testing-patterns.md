# Testing Patterns — Reference

This file is loaded on demand when the task involves writing or improving RSpec tests.

---

## Test Stack

| Tool | Purpose |
|---|---|
| RSpec | Test framework |
| FactoryBot | Test data generation |
| Faker | Realistic fake data |
| Capybara + Cuprite | System/E2E tests (headless Chrome) |
| SimpleCov | Coverage reporting |
| DatabaseCleaner | DB state management between tests |
| VCR + WebMock | HTTP request stubbing/recording |
| Action Policy RSpec | Authorization testing DSL |

---

## Directory Structure

```
spec/
├── rails_helper.rb          # Main helper, loads support files
├── spec_helper.rb           # RSpec core config
├── support/
│   ├── capybara.rb          # Capybara + Cuprite setup
│   ├── authorization_helpers.rb
│   └── ...
├── factories/               # FactoryBot factory definitions
├── models/                  # Model specs
├── services/                # Service object specs
├── requests/                # Request (controller) specs
│   ├── backoffice/
│   └── api/
├── policies/                # Policy specs
├── system/                  # System (Capybara) specs
└── jobs/                    # Background job specs
```

---

## Model Specs

```ruby
# spec/models/patient_spec.rb
RSpec.describe Patient, type: :model do
  describe "validations" do
    it { is_expected.to validate_presence_of(:first_name) }
  end

  describe "associations" do
    it { is_expected.to have_one(:patient_info).dependent(:destroy) }
    it { is_expected.to have_many(:pathway_patients) }
    it { is_expected.to have_many(:pathways).through(:pathway_patients) }
  end

  describe "#enroll_in!" do
    subject(:enrollment) { patient.pathway_patients.enroll_in!(pathway) }

    let(:patient) { create(:patient) }
    let(:pathway) { create(:pathway, :with_steps) }

    it "creates a pathway_patient record" do
      expect { enrollment }.to change { patient.pathway_patients.count }.by(1)
    end

    it "creates patient_steps for each pathway step" do
      expect { enrollment }.to change { PatientStep.count }.by(pathway.steps.count)
    end

    it "schedules email jobs for email template steps" do
      expect { enrollment }.to have_enqueued_job(PatientStepEmailsJob)
    end
  end
end
```

**Conventions:**
- Group by `describe "validations"`, `describe "associations"`, `describe "#method_name"` (instance), `describe ".method_name"` (class)
- Use `subject` for the action under test
- Use `let` / `let!` for test data (prefer `let` over `let!` unless eager loading is needed)
- Use `change` matcher for state transitions

---

## Service Specs

```ruby
# spec/services/backoffice/patient_steps/process_email_spec.rb
RSpec.describe Backoffice::PatientSteps::ProcessEmail do
  describe ".call" do
    let(:patient_step) { create(:patient_step, :scheduled) }

    context "when patient_step is scheduled" do
      it "sends the notification email" do
        expect {
          described_class.call(patient_step:)
        }.to have_enqueued_mail(PatientStepMailer, :step_email)
      end

      it "updates the patient_step status" do
        described_class.call(patient_step:)
        expect(patient_step.reload.status).to eq("notified")
      end
    end

    context "when patient_step is not scheduled" do
      let(:patient_step) { create(:patient_step, :completed) }

      it "does nothing" do
        expect {
          described_class.call(patient_step:)
        }.not_to have_enqueued_mail
      end
    end
  end
end
```

---

## Request Specs (Backoffice)

```ruby
# spec/requests/backoffice/pathways_spec.rb
RSpec.describe "Backoffice::Pathways", type: :request do
  let(:doctor) { create(:doctor) }

  before { sign_in doctor }

  describe "GET /admin/pathways" do
    let!(:pathway) { create(:pathway) }

    it "returns a successful response" do
      get backoffice_pathways_path
      expect(response).to have_http_status(:ok)
    end

    it "displays the pathway" do
      get backoffice_pathways_path
      expect(response.body).to include(pathway.name)
    end
  end

  describe "POST /admin/pathways" do
    let(:valid_params) { { pathway: { name: "New Pathway", status: "pending" } } }

    it "creates a new pathway" do
      expect {
        post backoffice_pathways_path, params: valid_params
      }.to change(Pathway, :count).by(1)
    end

    it "redirects to the new pathway" do
      post backoffice_pathways_path, params: valid_params
      expect(response).to redirect_to(backoffice_pathway_path(Pathway.last))
    end
  end

  describe "authorization" do
    context "when user is a patient" do
      let(:patient) { create(:patient) }

      before { sign_in patient }

      it "denies access" do
        get backoffice_pathways_path
        expect(response).to have_http_status(:redirect)
      end
    end
  end
end
```

**Conventions:**
- Use `Devise::Test::IntegrationHelpers` (included via `rails_helper.rb` for `type: :request`)
- Use `AuthorizationHelpers` for authorization testing
- Group by HTTP method and path: `describe "GET /admin/pathways"`
- Test both happy path and authorization failures
- Parse JSON with `JSON.parse(response.body)` for API specs

---

## Request Specs (API)

```ruby
# spec/requests/api/compiles_spec.rb
RSpec.describe "Api::Compiles", type: :request do
  let(:api_token) { create(:api_token) }
  let(:headers) { { "Authorization" => "Bearer #{api_token.token}" } }

  describe "GET /api/compiles" do
    let!(:answers) { create_list(:answer, 3, :completed) }

    it "returns completed answers" do
      get api_compiles_path, headers: headers
      expect(response).to have_http_status(:ok)

      json = JSON.parse(response.body)
      expect(json.size).to eq(3)
    end

    context "without authentication" do
      it "returns unauthorized" do
        get api_compiles_path
        expect(response).to have_http_status(:unauthorized)
      end
    end
  end
end
```

---

## Policy Specs

```ruby
# spec/policies/backoffice/pathway_policy_spec.rb
RSpec.describe Backoffice::PathwayPolicy, type: :policy do
  let(:pathway) { create(:pathway) }

  describe_rule :index? do
    succeed "when user is admin" do
      let(:user) { create(:admin) }
    end

    succeed "when user is doctor" do
      let(:user) { create(:doctor) }
    end

    failed "when user is patient" do
      let(:user) { create(:patient) }
    end
  end

  describe_rule :destroy? do
    succeed "when user is admin" do
      let(:user) { create(:admin) }
    end

    failed "when user is external clinician" do
      let(:user) { create(:doctor, external: true) }
    end
  end
end
```

---

## System Specs

```ruby
# spec/system/pathways/create_pathway_spec.rb
RSpec.describe "Creating a pathway", type: :system do
  let(:doctor) { create(:doctor) }

  before { sign_in doctor }

  it "allows a doctor to create a new pathway", :js do
    visit backoffice_pathways_path
    click_link "New Pathway"

    fill_in "Name", with: "Cardiac Rehabilitation"
    click_button "Save"

    expect(page).to have_content("Cardiac Rehabilitation")
    expect(page).to have_current_path(backoffice_pathway_path(Pathway.last))
  end
end
```

**Rules:**
- Tag with `:js` for JavaScript-dependent tests (uses Cuprite/Chrome)
- Use Warden helpers (`sign_in`) for authentication
- Prefer Capybara finders that wait: `have_content`, `have_current_path`
- See `e2e-testing-capybara` skill for detailed Capybara patterns

---

## Factories

```ruby
# spec/factories/users.rb
FactoryBot.define do
  factory :user do
    first_name { Faker::Name.first_name }
    last_name { Faker::Name.last_name }
    email { Faker::Internet.email }
    password { "password123" }
    confirmed_at { Time.zone.now }

    factory :admin, class: "Admin"
    factory :doctor, class: "Doctor" do
      trait :external do
        external { true }
      end
    end
    factory :patient, class: "Patient"
    factory :agency, class: "Agency"
  end
end
```

**Rules:**
- Define in `spec/factories/` — one file per model
- Use `Faker` for realistic data
- Use traits for variations (e.g. `:external`, `:with_steps`, `:completed`)
- Use `create` for persisted records, `build` for in-memory only
- Use `create_list(:model, n)` for collections
- Prefer `Time.zone.now` in factories, never `Time.now`

---

## Shared Examples

```ruby
# spec/support/shared_examples/authorization.rb
RSpec.shared_examples "requires authentication" do
  context "when not signed in" do
    before { sign_out :user }

    it "redirects to sign in" do
      make_request
      expect(response).to redirect_to(new_user_session_path)
    end
  end
end

# Usage in request spec:
describe "GET /admin/pathways" do
  it_behaves_like "requires authentication" do
    let(:make_request) { get backoffice_pathways_path }
  end
end
```

---

## Coverage

Run with coverage enabled:

```bash
COVERAGE=true bin/rspec
```

SimpleCov generates an HTML report in `coverage/`. Threshold: ≥80% on new code.
