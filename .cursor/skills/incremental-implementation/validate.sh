#!/usr/bin/env bash
# Local validation for Flask incremental implementation.
# Runs: pytest -> ruff check -> ruff format check -> optional mypy.

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

FAILED=0

echo "=== ianua-mind — Local Validation ==="
echo ""

echo "--- Running pytest ---"
pytest -q || FAILED=1

echo ""
echo "--- Running ruff check ---"
ruff check . || FAILED=1

echo ""
echo "--- Running ruff format --check ---"
ruff format --check . || FAILED=1

if command -v mypy >/dev/null 2>&1; then
  echo ""
  echo "--- Running mypy app/ (optional) ---"
  mypy app/ || FAILED=1
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "=== All checks passed. Ready to commit. ==="
else
  echo "=== Some checks failed. Fix issues before committing. ==="
  exit 1
fi
