---
name: e2e-testing-capybara
description: >-
  Create and run end-to-end system tests using Capybara with Cuprite (headless Chrome via Ferrum).
  Use when writing system specs, browser automation, Turbo/Hotwire UI flows, or when asked for
  E2E tests, Capybara tests, or integration tests with a real browser (this stack is not Playwright).
---

# E2E Testing with Capybara + Cuprite

Full browser automation using Capybara + Cuprite (headless Chrome via Ferrum/CDP).

## Setup Requirements

Add to `Gemfile` (group: test):
```ruby
gem "capybara"
gem "cuprite"
```

Create `spec/support/capybara.rb`:
```ruby
require "capybara/rspec"
require "capybara/cuprite"

Capybara.register_driver(:cuprite) do |app|
  Capybara::Cuprite::Driver.new(
    app,
    window_size: [1200, 800],
    browser_options: { "no-sandbox": nil },
    headless: !ENV["HEADED"],
    slowmo: ENV["SLOWMO"]&.to_f,
    inspector: ENV["INSPECTOR"]
  )
end

Capybara.default_driver = :rack_test        # Fast for non-JS specs
Capybara.javascript_driver = :cuprite       # Chrome for JS specs
Capybara.default_max_wait_time = 5
Capybara.server = :puma, { Silent: true }
```

Require in `spec/rails_helper.rb`:
```ruby
require "support/capybara"
```

## Test Structure

System specs live in `spec/system/`. One file per user journey or feature.

```ruby
# spec/system/pathways/step_management_spec.rb
RSpec.describe "Pathway Step Management", type: :system do
  let(:doctor) { create(:doctor) }
  let(:pathway) { create(:pathway) }

  before { sign_in doctor }

  it "allows doctor to reorder steps via drag-and-drop", :js do
    visit backoffice_pathway_steps_path(pathway)

    # ... interact with page
    expect(page).to have_content("Order saved")
  end
end
```

## Conventions

### Tagging
- Use `:js` tag for tests requiring JavaScript (uses Cuprite driver)
- Tests without `:js` use rack_test (faster, for non-JS features)

### Setup Pattern (Arrange → Act → Assert)
```ruby
it "creates a survey assignment" do
  # Arrange: data already set up in let/before blocks

  # Act: navigate and interact
  visit new_backoffice_patient_survey_path(@patient)
  select "Patient Satisfaction", from: "Survey"
  click_button "Assign Survey"

  # Assert: verify outcome
  expect(page).to have_content("Survey assigned successfully")
  expect(page).to have_current_path(backoffice_patient_surveys_path(@patient))
end
```

### Waiting for Turbo
Capybara automatically waits for DOM changes. For Turbo navigation:
```ruby
expect(page).to have_current_path(expected_path)  # waits for navigation
expect(page).to have_content("text")               # waits for content
```

### Page Object Pattern (for complex pages)
```ruby
# spec/support/page_objects/pathway_page.rb
class PathwayPage
  include Capybara::DSL

  def initialize(pathway)
    @pathway = pathway
    visit backoffice_pathway_path(pathway)
  end

  def add_step(name:)
    click_link "Add Step"
    fill_in "Name", with: name
    click_button "Save Step"
    self
  end

  def expect_step(name)
    expect(page).to have_content(name)
    self
  end
end
```

### Authentication in System Specs
```ruby
# Use Warden test helpers (included via Devise)
before { sign_in user }

# Or use the login page flow for testing auth itself
it "redirects unauthenticated users" do
  visit backoffice_root_path
  expect(page).to have_current_path(new_user_session_path)
end
```

## Running System Tests

```bash
# All system specs
bin/rspec spec/system/

# Single file
bin/rspec spec/system/pathways/step_management_spec.rb

# With visible browser (debug mode)
HEADED=true bin/rspec spec/system/

# Slow motion for debugging
HEADED=true SLOWMO=0.5 bin/rspec spec/system/

# With Chrome DevTools inspector
HEADED=true INSPECTOR=true bin/rspec spec/system/
```

## Common Scenarios to Test

For each major feature, create system specs covering:
1. **Happy path**: main user journey from start to finish
2. **Validation errors**: form submission with invalid data
3. **Authorization**: unauthenticated and unauthorized access
4. **Turbo updates**: AJAX/Turbo Frame interactions

## Setup Guide

For detailed installation and Chrome configuration, see [setup-guide.md](setup-guide.md).
