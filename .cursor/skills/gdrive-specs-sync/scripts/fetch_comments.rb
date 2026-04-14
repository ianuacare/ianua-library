#!/usr/bin/env ruby
# frozen_string_literal: true

# Fetches and displays comments from a Google Docs spec document.
#
# Usage:
#   ruby fetch_comments.rb specs/features/my-feature.md
#   ruby fetch_comments.rb <google_doc_id>
#
# Requirements:
#   - GDRIVE_SERVICE_ACCOUNT_PATH env var
#   - Gems: google-apis-drive_v3

require "bundler/setup"
require "google/apis/drive_v3"
require "googleauth"
require "yaml"
require "json"

def abbreviate_text(str, max)
  return "" if str.nil?

  s = str.to_s
  s.length > max ? "#{s[0, max]}..." : s
end

# ── Resolve Document ID ───────────────────────────────────────────────────────

input = ARGV[0]
abort("Usage: fetch_comments.rb SPEC_FILE_OR_DOC_ID") unless input

doc_id = if File.exist?(input)
  content = File.read(input)
  frontmatter_match = content.match(/\A---\n(.*?)\n---\n/m)
  abort("No frontmatter found in #{input}") unless frontmatter_match

  metadata = YAML.safe_load(frontmatter_match[1])
  gdrive_url = metadata["gdrive_url"]
  abort("No gdrive_url found in spec frontmatter. Publish the spec first.") unless gdrive_url

  gdrive_url.match(%r{/document/d/([^/]+)})&.[](1).tap do |id|
    abort("Could not extract document ID from URL: #{gdrive_url}") unless id
  end
else
  input
end

puts "Fetching comments from document: #{doc_id}"

# ── Google API Auth ───────────────────────────────────────────────────────────

service_account_path = ENV.fetch("GDRIVE_SERVICE_ACCOUNT_PATH") { abort("GDRIVE_SERVICE_ACCOUNT_PATH not set") }

auth = Google::Auth::ServiceAccountCredentials.make_creds(
  json_key_io: File.open(service_account_path),
  scope: Google::Apis::DriveV3::AUTH_DRIVE_READONLY
)

drive = Google::Apis::DriveV3::DriveService.new
drive.authorization = auth

# ── Fetch Comments ────────────────────────────────────────────────────────────

comments_response = drive.list_comments(
  doc_id,
  fields: "comments(id,author,content,resolved,quotedFileContent,replies,createdTime,modifiedTime)",
  include_deleted: false
)

comments = comments_response.comments || []

if comments.empty?
  puts ""
  puts "No open comments found on this document."
  exit 0
end

# ── Display Comments ──────────────────────────────────────────────────────────

open_count = comments.count { |c| !c.resolved }
resolved_count = comments.count(&:resolved)

puts ""
puts "=" * 60
puts "COMMENTS SUMMARY"
puts "=" * 60
puts "Total: #{comments.length} | Open: #{open_count} | Resolved: #{resolved_count}"
puts "=" * 60

comments.each_with_index do |comment, i|
  status = comment.resolved ? "[RESOLVED]" : "[OPEN]"
  puts ""
  puts "#{i + 1}. #{status} — #{comment.author&.display_name || 'Unknown'}"
  puts "   Date: #{comment.created_time&.strftime('%Y-%m-%d %H:%M')}"

  if comment.quoted_file_content
    quoted = abbreviate_text(comment.quoted_file_content.value, 100)
    puts "   Quoted text: \"#{quoted}\""
  end

  puts "   Comment: #{comment.content}"

  if comment.replies&.any?
    comment.replies.each do |reply|
      puts "   └─ #{reply.author&.display_name}: #{reply.content}"
    end
  end
end

puts ""
puts "=" * 60

if open_count > 0
  puts ""
  puts "ACTION REQUIRED:"
  puts "#{open_count} open comment(s) need to be addressed."
  puts ""
  puts "For each open comment:"
  puts "1. Update the spec: specs/features/<name>.md"
  puts "2. Re-publish: ruby .cursor/skills/gdrive-specs-sync/scripts/publish_spec.rb <spec> --update"
  puts "3. Resolve the comment in Google Docs"
end
