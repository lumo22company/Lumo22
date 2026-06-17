#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/sophieoverment/LUMO22"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/niche_pipeline.log"

# Default schedule: 06:00 local time every day.
CRON_EXPR="${1:-0 6 * * *}"

mkdir -p "$LOG_DIR"

JOB="$CRON_EXPR cd $PROJECT_ROOT && /usr/bin/python3 scripts/run_niche_pipeline.py --config configs/niches.json >> $LOG_FILE 2>&1"

# Install idempotently: remove older line for this script path, then append new one.
(crontab -l 2>/dev/null | awk '!/scripts\/run_niche_pipeline\.py --config configs\/niches\.json/'; echo "$JOB") | crontab -

echo "Installed cron job:"
echo "$JOB"
echo "Logs: $LOG_FILE"
