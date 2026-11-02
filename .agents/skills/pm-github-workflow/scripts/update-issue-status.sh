#!/usr/bin/env bash
set -euo pipefail

# Updates a GitHub issue's Status field on a project board.
# Reads all project-specific values from pm-config.json.
#
# Usage: update-issue-status.sh <issue-number> <status>
# Valid statuses: backlog, ready, in-progress, in-review, done
#
# Dependencies: gh CLI (authenticated), python3 (stdlib only)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../pm-config.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: Config file not found at $CONFIG_FILE" >&2
  echo "Copy pm-config.example.json to pm-config.json and fill in your project values." >&2
  exit 1
fi

ISSUE_NUM="${1:?Usage: update-issue-status.sh <issue-number> <status>}"
STATUS="${2:?Usage: update-issue-status.sh <issue-number> <status>}"

# Read config values via python3 (stdlib only)
read_config() {
  python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
key = sys.argv[1]
if key == 'org':
    print(cfg['github']['org'])
elif key == 'project_number':
    print(cfg['github']['project_number'])
elif key == 'field_id':
    print(cfg['project_fields']['status']['field_id'])
elif key == 'option_id':
    status = sys.argv[2]
    opts = cfg['project_fields']['status']['options']
    if status not in opts:
        print('', end='')
        sys.exit(1)
    print(opts[status])
" "$@"
}

ORG=$(read_config org)
PROJECT_NUMBER=$(read_config project_number)
FIELD_ID=$(read_config field_id)
OPTION_ID=$(read_config option_id "$STATUS") || true

if [[ -z "$OPTION_ID" ]]; then
  echo "ERROR: Invalid status '$STATUS'. Valid: backlog, ready, in-progress, in-review, done" >&2
  exit 1
fi

PROJECT_ID=$(gh project list --owner "$ORG" --format json \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for p in data['projects']:
    if p['number'] == $PROJECT_NUMBER:
        print(p['id'])
        break
")

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: Could not find project #${PROJECT_NUMBER} in ${ORG}" >&2
  exit 1
fi

ITEM_ID=$(gh project item-list "$PROJECT_NUMBER" --owner "$ORG" --limit 200 --format json \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for i in data['items']:
    if i.get('content', {}).get('number') == ${ISSUE_NUM}:
        print(i['id'])
        break
")

if [[ -z "$ITEM_ID" ]]; then
  echo "ERROR: Issue #${ISSUE_NUM} not found in project board" >&2
  exit 1
fi

gh project item-edit \
  --project-id "$PROJECT_ID" \
  --id "$ITEM_ID" \
  --field-id "$FIELD_ID" \
  --single-select-option-id "$OPTION_ID"

echo "Issue #${ISSUE_NUM} → ${STATUS} (option: ${OPTION_ID})"
