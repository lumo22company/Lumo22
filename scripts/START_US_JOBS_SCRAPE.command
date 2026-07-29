#!/bin/bash
# Double-click or: ./scripts/START_US_JOBS_SCRAPE.command
cd "$(dirname "$0")/.." || exit 1
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
DATE=$(date +%Y-%m-%d)
mkdir -p exports
echo "=== US jobs scrape (Apify, max 250/query, 14-day window) ==="
echo "Folder: $(pwd)"
echo "Date:   $DATE"
echo ""
python3 -u scripts/scrape_job_intent.py \
  --use-apify \
  --us-only \
  --us-broad-only \
  --apify-max-results 250 \
  --hours-old 336 \
  --date "$DATE" \
  2>&1 | tee "exports/jobs_us_scrape_${DATE}.log"
echo ""
echo "=== Finished. Press Enter to close. ==="
read -r
