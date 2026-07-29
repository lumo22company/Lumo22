#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
echo "=== US jobs email finish (local probe) ==="
echo "Folder: $(pwd)"
echo ""
python3 -u scripts/us_jobs_finish.py --skip-apify --limit 168 2>&1 | tee exports/us_jobs_finish_2026-07-02.log
echo ""
echo "=== Finished. Press Enter to close. ==="
read -r
