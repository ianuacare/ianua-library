---
name: gdrive-specs-sync
description: >-
  Sync feature specifications between local /specs folder and Google Drive/Docs
  for stakeholder review and feedback collection. Use when publishing a spec for
  review, collecting stakeholder feedback from Google Docs comments, updating local
  specs from external input, or managing the spec review lifecycle with business owners.
---

# Google Drive Specs Sync

Bidirectional sync between `specs/features/` markdown files and Google Docs.

## Prerequisites

Before using this skill, ensure:
1. Google Cloud project with Drive API and Docs API enabled
2. Service account JSON at `config/credentials/gdrive-service-account.json` (gitignored; path from `GDRIVE_SERVICE_ACCOUNT_PATH`)
3. `GDRIVE_SPECS_FOLDER_ID` set in `.env`
4. Required gems installed (see setup below)

**Setup**: See [setup-guide.md](setup-guide.md) for full installation instructions.

## Publishing a Spec to Google Drive

### Step 1 — Verify Spec Readiness
Check that the spec in `specs/features/<name>.md`:
- Has `status: draft` or ready to promote to `review`
- Has all required sections filled (not template placeholders)
- Has been reviewed internally

### Step 2 — Publish

```bash
ruby .cursor/skills/gdrive-specs-sync/scripts/publish_spec.rb specs/features/<name>.md
```

The script will:
1. Convert markdown to Google Docs format
2. Upload to the shared Drive folder (`GDRIVE_SPECS_FOLDER_ID`)
3. Set sharing permissions (view for stakeholders)
4. Print the Google Docs URL

### Step 3 — Update Spec Frontmatter
Update the local spec with the returned URL:
```yaml
status: review
gdrive_url: "https://docs.google.com/document/d/..."
```

### Step 4 — Notify Stakeholders
Share the URL with the Business Owner for review. They can add comments directly in Google Docs.

## Collecting Feedback from Google Docs

When stakeholders have added comments to the Google Doc:

### Step 1 — Fetch Comments

```bash
ruby .cursor/skills/gdrive-specs-sync/scripts/fetch_comments.rb <gdrive_doc_id>
```

The script extracts the doc ID from `gdrive_url` in the spec frontmatter.

### Step 2 — Review and Apply
The script outputs a structured list of comments:
```
Comment by: Stakeholder Name
Section: "Requisiti Funzionali"
Comment: "RF-02 non è chiaro, specificare il formato della data"
Action: [OPEN/RESOLVED]
```

For each open comment:
1. Discuss with the user if clarification is needed
2. Update the relevant section of `specs/features/<name>.md`
3. Mark the comment as resolved in the Google Doc

### Step 3 — Re-publish

After applying feedback:
```bash
ruby .cursor/skills/gdrive-specs-sync/scripts/publish_spec.rb specs/features/<name>.md --update
```

This updates the existing Google Doc (preserves comment history) rather than creating a new one.

### Step 4 — Update Status
When all feedback is addressed and stakeholder approves:
```yaml
status: approved
```

## Lifecycle States

| Transition | Action |
|-----------|--------|
| `draft` → `review` | Publish to Google Drive, share link |
| `review` → `review` | Collect feedback, update spec, re-publish |
| `review` → `approved` | Stakeholder signs off, update frontmatter |
| `approved` → `in-progress` | Use `spec-driven-planning` to create GitHub issues |
| `in-progress` → `implemented` | Feature shipped, update frontmatter |

## Configuration

| Setting | Location | Description |
|---------|---------|-------------|
| `GDRIVE_SPECS_FOLDER_ID` | `.env` | Target Google Drive folder for specs |
| Service account key | `config/credentials/gdrive-service-account.json` (see `.env.sample`) | Never commit; use `.gitignore` |
| Stakeholder emails | Script param `--share` | Comma-separated list for sharing |

## Scripts Reference

- **publish_spec.rb**: Upload/update spec to Google Drive
- **fetch_comments.rb**: Retrieve and parse comments from Google Docs

See [setup-guide.md](setup-guide.md) for installation and authentication setup.
