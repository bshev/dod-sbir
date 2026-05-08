#!/usr/bin/env bash
# Cron wrapper for the DoD SBIR scraper.
#
# Setup:
#   1. Fill in PROJECT_DIR and POETRY below.
#      Run `which poetry` on the server to find the poetry path.
#   2. chmod +x run_scraper.sh
#   3. Add to crontab with: crontab -e
#      Then add this line (runs daily at 6am server time):
#        0 6 * * * /path/to/dod-sbir/run_scraper.sh

set -euo pipefail

PROJECT_DIR="/home/user/dod-sbir"          # <-- change to actual server path
POETRY="/home/user/.local/bin/poetry"       # <-- run `which poetry` on server to confirm

LOG_FILE="$PROJECT_DIR/scraper.log"
MAX_LOG_LINES=5000                          # keep log from growing unbounded

cd "$PROJECT_DIR"

echo "--- $(date '+%Y-%m-%d %H:%M:%S') start ---" >> "$LOG_FILE"
"$POETRY" run python main.py >> "$LOG_FILE" 2>&1
echo "--- $(date '+%Y-%m-%d %H:%M:%S') done ---" >> "$LOG_FILE"

# Trim log to last MAX_LOG_LINES lines
if [ "$(wc -l < "$LOG_FILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
