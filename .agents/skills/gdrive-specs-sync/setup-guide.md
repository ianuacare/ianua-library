# Google Drive Sync Setup Guide

## 1. Google Cloud Setup

### Create a Project and Enable APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable these APIs:
   - Google Drive API
   - Google Docs API

### Create a Service Account

1. Navigate to IAM & Admin → Service Accounts
2. Click "Create Service Account"
3. Name: `easydoctor-specs-sync`
4. Grant role: none (will use Drive sharing instead)
5. Create and download JSON key
6. Move the file to **`config/credentials/gdrive-service-account.json`** (canonical path; matches `GDRIVE_SERVICE_ACCOUNT_PATH` in `.env.sample`). You may download to `tmp/` first, then `mv` — never commit the JSON.

### Configure Drive Folder Sharing

1. Create a folder in Google Drive: "EasyDoctor Specs"
2. Share it with the service account email (from the JSON key): give "Editor" access
3. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`

## 2. Store Credentials Securely

```bash
# Add to Rails encrypted credentials (never commit plain JSON)
bin/rails credentials:edit

# Add this section:
# gdrive:
#   service_account: '<paste full JSON content as single line or use file reference>'
```

Or for simplicity during development, store in `.env` (add to `.gitignore`):
```bash
GDRIVE_SERVICE_ACCOUNT_PATH=config/credentials/gdrive-service-account.json
GDRIVE_SPECS_FOLDER_ID=your-folder-id-here
```

Add to `.env.sample`:
```bash
GDRIVE_SPECS_FOLDER_ID=your-google-drive-folder-id
GDRIVE_SERVICE_ACCOUNT_PATH=config/credentials/gdrive-service-account.json
```

## 3. Add Required Gems

Add to `Gemfile` (all environments or development-only):

```ruby
# Google APIs for spec sync
gem "google-apis-drive_v3"
gem "google-apis-docs_v1"
gem "kramdown"  # Markdown to HTML conversion
```

Run:
```bash
bundle install
```

## 4. Script Installation

The scripts in `.cursor/skills/gdrive-specs-sync/scripts/` are standalone Ruby scripts.
They use the gems above. No additional installation needed after `bundle install`.

Make them executable:
```bash
chmod +x .cursor/skills/gdrive-specs-sync/scripts/publish_spec.rb
chmod +x .cursor/skills/gdrive-specs-sync/scripts/fetch_comments.rb
```

## 5. Test the Connection

```bash
# Test authentication
ruby -e "
require 'google/apis/drive_v3'
require 'googleauth'

scope = Google::Apis::DriveV3::AUTH_DRIVE
auth = Google::Auth::ServiceAccountCredentials.make_creds(
  json_key_io: File.open(ENV['GDRIVE_SERVICE_ACCOUNT_PATH']),
  scope: scope
)
service = Google::Apis::DriveV3::DriveService.new
service.authorization = auth
files = service.list_files(q: \"'#{ENV['GDRIVE_SPECS_FOLDER_ID']}' in parents\")
puts 'Connection successful! Files in folder: ' + files.files.map(&:name).inspect
"
```

## 6. Sharing with Stakeholders

The `publish_spec.rb` script accepts a `--share` flag:

```bash
ruby .cursor/skills/gdrive-specs-sync/scripts/publish_spec.rb \
  specs/features/my-feature.md \
  --share stakeholder@example.com,other@example.com
```

This sets `reader` permission for the specified emails on the uploaded document.

## Security Notes

- The service account JSON key must NEVER be committed to git
- Add `config/credentials/gdrive-service-account.json` to `.gitignore`
- In production/CI, use environment variables or encrypted credentials
- The service account only has access to the explicitly shared folder, not the entire Drive
