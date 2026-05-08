#!/usr/bin/env bash
# Cron wrapper for the DoD SBIR scraper.
#
# Setup:
#   1. Copy .env.example to .env and fill in PROJECT_DIR and POETRY.
#      Run `which poetry` on the server to find the poetry path.
#   2. chmod +x run_scraper.sh
#   3. Add to crontab with: crontab -e
#      Then add this line (runs daily at 6am server time):
#        0 6 * * * /home/user/dod-sbir/run_scraper.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env from project root
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env"; set +a
else
    echo "Error: .env not found. Copy .env.example to .env and fill in values." >&2
    exit 1
fi

LOG_FILE="$PROJECT_DIR/scraper.log"
MAX_LOG_LINES=5000

cd "$PROJECT_DIR"

echo "--- $(date '+%Y-%m-%d %H:%M:%S') start ---" >> "$LOG_FILE"
"$POETRY" run python main.py >> "$LOG_FILE" 2>&1
echo "--- $(date '+%Y-%m-%d %H:%M:%S') done ---" >> "$LOG_FILE"

# Trim log to last MAX_LOG_LINES lines
if [ "$(wc -l < "$LOG_FILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
