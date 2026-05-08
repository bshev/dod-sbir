#!/usr/bin/env bash
# Pull a fresh dod_sbir.db from the server. scores.db is local-only and untouched.
# Usage: ./pull_db.sh
# Configure REMOTE_USER, REMOTE_HOST, REMOTE_DB_PATH in .env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env from project root
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env"; set +a
else
    echo "Error: .env not found. Copy .env.example to .env and fill in values." >&2
    exit 1
fi

echo "Pulling dod_sbir.db from $REMOTE_USER@$REMOTE_HOST..."
scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DB_PATH" "$SCRIPT_DIR/dod_sbir.db"
echo "Done. scores.db untouched."
