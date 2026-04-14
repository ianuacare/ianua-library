#!/usr/bin/env bash
# Local validation script for incremental-implementation skill.
# Runs: rspec (changed files) → rubocop → brakeman → i18n check
# Usage: bash .cursor/skills/incremental-implementation/validate.sh [spec_path]

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

SPEC_PATH="${1:-}"
FAILED=0

echo "=== EasyDoctor Local Validation ==="
echo ""

# 1. RSpec
echo "--- Running RSpec ---"
if [ -n "$SPEC_PATH" ]; then
  echo "Running: bin/rspec $SPEC_PATH"
  bin/rspec "$SPEC_PATH" || FAILED=1
else
  echo "Running: bin/rspec (full suite)"
  bin/rspec || FAILED=1
fi

# 2. RuboCop (only changed files)
echo ""
echo "--- Running RuboCop (changed files) ---"
# Unstaged + staged Ruby changes (union); avoids missing files only in the index
CHANGED_RUBY=$(
  { git diff --name-only -- '*.rb'; git diff --name-only --cached -- '*.rb'; } | sort -u | tr '\n' ' '
)
if [ -n "$CHANGED_RUBY" ]; then
  echo "Running: bin/rubocop $CHANGED_RUBY"
  # shellcheck disable=SC2086
  bin/rubocop $CHANGED_RUBY || FAILED=1
else
  echo "No changed Ruby files detected."
fi

# 3. Brakeman
echo ""
echo "--- Running Brakeman ---"
bin/brakeman -q -w2 || FAILED=1

# 4. i18n (only if locale files changed)
CHANGED_LOCALES=$(
  { git diff --name-only -- 'config/locales/**'; git diff --name-only --cached -- 'config/locales/**'; } | sort -u | wc -l
)
if [ "$CHANGED_LOCALES" -gt 0 ]; then
  echo ""
  echo "--- Running i18n health check ---"
  bundle exec i18n-tasks health || FAILED=1
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "=== All checks passed. Ready to commit! ==="
else
  echo "=== Some checks failed. Fix issues before committing. ==="
  exit 1
fi
