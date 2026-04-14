# E2E Testing Setup Guide

Complete setup guide for Capybara + Cuprite in the EasyDoctor project.

## 1. Add Gems

Add to `Gemfile` in the `group :test do` block:

```ruby
group :test do
  # existing gems...
  gem "capybara"
  gem "cuprite"
end
```

Run:
```bash
bundle install
```

## 2. Install Chrome/Chromium

Cuprite requires Chrome or Chromium:

```bash
# Ubuntu/Debian (WSL included)
sudo apt-get install -y chromium-browser
# or
sudo apt-get install -y google-chrome-stable

# macOS
brew install --cask google-chrome

# Verify
google-chrome --version
# or
chromium --version
```

## 3. Create Capybara Support File

Create `spec/support/capybara.rb`:

```ruby
# frozen_string_literal: true

require "capybara/rspec"
require "capybara/cuprite"

# Configure Cuprite driver
Capybara.register_driver(:cuprite) do |app|
  Capybara::Cuprite::Driver.new(
    app,
    window_size: [1200, 800],
    browser_options: {
      "no-sandbox": nil,
      "disable-dev-shm-usage": nil  # Required in Docker/CI environments
    },
    headless: !ENV["HEADED"],
    slowmo: ENV["SLOWMO"]&.to_f,
    inspector: ENV["INSPECTOR"],
    timeout: 10
  )
end

# Default: rack_test for non-JS, cuprite for JS (:js tag)
Capybara.default_driver = :rack_test
Capybara.javascript_driver = :cuprite
Capybara.default_max_wait_time = 5
Capybara.server = :puma, { Silent: true }
Capybara.asset_host = "http://localhost:3000"

RSpec.configure do |config|
  config.include Capybara::DSL, type: :system
end
```

## 4. Update `spec/rails_helper.rb`

Add this require after the existing support file requires:

```ruby
require "support/capybara"
```

## 5. Add Page Objects Directory

```bash
mkdir -p spec/support/page_objects
```

Add to `spec/rails_helper.rb`:
```ruby
# Already covered by: Rails.root.glob("spec/support/**/*.rb").each { |f| require f }
# But if using explicit requires, add:
# require "support/page_objects/pathway_page"
```

## 6. Create First System Spec

```bash
mkdir -p spec/system
```

Example `spec/system/auth/sign_in_spec.rb`:

```ruby
# frozen_string_literal: true

RSpec.describe "Sign In", type: :system do
  let(:doctor) { create(:doctor) }

  it "allows doctor to sign in with valid credentials" do
    visit new_user_session_path

    fill_in "Email", with: doctor.email
    fill_in "Password", with: "password"
    click_button "Sign in"

    expect(page).to have_current_path(backoffice_dashboard_index_path)
    expect(page).to have_content(doctor.name)
  end

  it "shows error for invalid credentials" do
    visit new_user_session_path

    fill_in "Email", with: doctor.email
    fill_in "Password", with: "wrong-password"
    click_button "Sign in"

    expect(page).to have_content("Invalid Email or password")
    expect(page).to have_current_path(new_user_session_path)
  end
end
```

## 7. CI Configuration

Add to `.github/workflows/_tests.yml` for running system tests in CI:

```yaml
- name: Install Chrome
  run: |
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable

- name: Run system tests
  env:
    CHROME_PATH: /usr/bin/google-chrome
  run: bin/rspec spec/system/
```

## 8. DatabaseCleaner for System Tests

EasyDoctor already configures DatabaseCleaner in [`spec/support/database_cleaner.rb`](../../../spec/support/database_cleaner.rb). Capybara **:js** specs use a real server and threads, so **transaction** strategy can break — use **truncation** for `type: :system`.

Replace the entire `RSpec.configure` block in that file with:

```ruby
# frozen_string_literal: true

RSpec.configure do |config|
  config.before(:suite) do
    DatabaseCleaner.clean_with :truncation, except: %w[ar_internal_metadata]
  end

  config.before(:each) do |example|
    DatabaseCleaner.strategy = example.metadata[:type] == :system ? :truncation : :transaction
    DatabaseCleaner.start
  end

  config.after(:each) do
    DatabaseCleaner.clean
  end
end
```

This keeps the existing `except: %w[ar_internal_metadata]` behavior and only changes per-example strategy selection.

## Troubleshooting

### Chrome not found
```bash
# Set CHROME_PATH if Chrome is in a non-standard location
export CHROME_PATH=/usr/bin/chromium-browser
```

### Timeout errors
Increase `Capybara.default_max_wait_time` for slow CI environments:
```ruby
Capybara.default_max_wait_time = 10
```

### JavaScript not loading
Ensure assets are precompiled or the test server serves them:
```bash
RAILS_ENV=test bin/rails assets:precompile
```

### Screenshots on failure
Cuprite automatically saves screenshots on failure in `tmp/screenshots/`.
