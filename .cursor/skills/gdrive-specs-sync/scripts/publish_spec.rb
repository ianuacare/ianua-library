#!/usr/bin/env ruby
# frozen_string_literal: true

# Publishes or updates a feature spec markdown file to Google Drive.
#
# Usage:
#   ruby publish_spec.rb specs/features/my-feature.md [--update] [--share email1,email2]
#
# Requirements:
#   - GDRIVE_SPECS_FOLDER_ID env var
#   - GDRIVE_SERVICE_ACCOUNT_PATH env var (path to service account JSON)
#   - Gems: google-apis-drive_v3, google-apis-docs_v1, kramdown

require "bundler/setup"
require "google/apis/drive_v3"
require "google/apis/docs_v1"
require "googleauth"
require "kramdown"
require "yaml"
require "optparse"
require "pathname"

# ── CLI Options ──────────────────────────────────────────────────────────────

options = { update: false, share: [] }
parser = OptionParser.new do |opts|
  opts.banner = "Usage: publish_spec.rb SPEC_FILE [options]"
  opts.on("--update", "Update existing doc instead of creating new") { options[:update] = true }
  opts.on("--share EMAILS", "Comma-separated emails to share with") do |emails|
    options[:share] = emails.split(",").map(&:strip)
  end
end
parser.parse!

spec_file = ARGV[0]
abort(parser.to_s) unless spec_file
abort("File not found: #{spec_file}") unless File.exist?(spec_file)

# ── Read Spec ────────────────────────────────────────────────────────────────

content = File.read(spec_file)
frontmatter_match = content.match(/\A---\n(.*?)\n---\n(.*)\z/m)
abort("Invalid spec file: missing YAML frontmatter") unless frontmatter_match

metadata = YAML.safe_load(frontmatter_match[1])
markdown_body = frontmatter_match[2]
title = metadata["title"] || File.basename(spec_file, ".md").tr("-", " ").capitalize

puts "Publishing spec: #{title}"
puts "File: #{spec_file}"

# ── Google APIs Auth ─────────────────────────────────────────────────────────

folder_id = ENV.fetch("GDRIVE_SPECS_FOLDER_ID") { abort("GDRIVE_SPECS_FOLDER_ID not set") }
service_account_path = ENV.fetch("GDRIVE_SERVICE_ACCOUNT_PATH") { abort("GDRIVE_SERVICE_ACCOUNT_PATH not set") }

scopes = [
  Google::Apis::DriveV3::AUTH_DRIVE,
  Google::Apis::DocsV1::AUTH_DOCUMENTS
]

auth = Google::Auth::ServiceAccountCredentials.make_creds(
  json_key_io: File.open(service_account_path),
  scope: scopes
)

drive = Google::Apis::DriveV3::DriveService.new
drive.authorization = auth

docs = Google::Apis::DocsV1::DocsService.new
docs.authorization = auth

# ── Create or Update Document ────────────────────────────────────────────────

existing_doc_id = metadata["gdrive_url"]&.match(%r{/document/d/([^/]+)})&.[](1)

if options[:update] && existing_doc_id
  puts "Updating existing document: #{existing_doc_id}"
  doc_id = existing_doc_id

  # Clear existing content and replace
  doc = docs.get_document(doc_id)
  end_index = doc.body.content.last.end_index - 1

  if end_index > 1
    requests = [
      { delete_content_range: { range: { start_index: 1, end_index: } } }
    ]
    docs.batch_update_document(doc_id, Google::Apis::DocsV1::BatchUpdateDocumentRequest.new(requests:))
  end
else
  puts "Creating new document..."
  file_metadata = Google::Apis::DriveV3::File.new(
    name: "SPEC: #{title}",
    mime_type: "application/vnd.google-apps.document",
    parents: [folder_id]
  )
  file = drive.create_file(file_metadata, fields: "id")
  doc_id = file.id
  puts "Created document: #{doc_id}"
end

# ── Insert Content ────────────────────────────────────────────────────────────

# Convert markdown to plain text with structure for Google Docs
# (Full rich formatting would require complex Docs API requests)
plain_content = markdown_body
  .gsub(/^#{1,6}\s+(.+)$/) { "#{$1}\n" }
  .gsub(/\*\*(.+?)\*\*/, '\1')
  .gsub(/\*(.+?)\*/, '\1')
  .gsub(/`(.+?)`/, '\1')
  .gsub(/^\s*[-*]\s+/, "• ")
  .gsub(/^\s*\d+\.\s+/, "")
  .strip

insert_text_request = {
  insert_text: {
    location: { index: 1 },
    text: "#{title}\n\n#{plain_content}\n"
  }
}

docs.batch_update_document(
  doc_id,
  Google::Apis::DocsV1::BatchUpdateDocumentRequest.new(requests: [insert_text_request])
)

# ── Set Sharing Permissions ───────────────────────────────────────────────────

options[:share].each do |email|
  permission = Google::Apis::DriveV3::Permission.new(
    type: "user",
    role: "reader",
    email_address: email
  )
  drive.create_permission(doc_id, permission, send_notification_email: true)
  puts "Shared with: #{email}"
end

# ── Output Result ─────────────────────────────────────────────────────────────

doc_url = "https://docs.google.com/document/d/#{doc_id}/edit"
puts ""
puts "Document published successfully!"
puts "URL: #{doc_url}"
puts ""
puts "Update your spec frontmatter:"
puts "  gdrive_url: \"#{doc_url}\""
puts "  status: review"
