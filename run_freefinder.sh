#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/guppycoder/Code/FreeFinder"
cd "$PROJECT_DIR"

# Load local env vars (not committed); preserves spaces in values.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Allow overriding defaults via env if desired
POSTAL="${POSTAL:-78254}"
SEARCH_DISTANCE="${SEARCH_DISTANCE:-30}"
MAX_ITEMS="${MAX_ITEMS:-120}"

source .venv/bin/activate
.venv/bin/python cli.py \
  --postal "$POSTAL" \
  --search-distance "$SEARCH_DISTANCE" \
  --max-items "$MAX_ITEMS" \
  --email-to "${EMAIL_TO:?EMAIL_TO must be set}" \
  --email-from "${EMAIL_FROM:?EMAIL_FROM must be set}"
