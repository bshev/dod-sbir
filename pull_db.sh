#!/usr/bin/env bash
# Pull a fresh dod_sbir.db from the server. scores.db is local-only and untouched.
# Usage: ./pull_db.sh [user@host]
#
# Set REMOTE_PATH to wherever dod_sbir.db lives on the server.

REMOTE=${1:-"user@yourserver"}
REMOTE_PATH="/path/to/dod-sbir/dod_sbir.db"
LOCAL_PATH="$(cd "$(dirname "$0")" && pwd)/dod_sbir.db"

echo "Pulling dod_sbir.db from $REMOTE..."
scp "$REMOTE:$REMOTE_PATH" "$LOCAL_PATH"
echo "Done. scores.db untouched."
