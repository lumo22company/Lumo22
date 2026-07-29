#!/usr/bin/env bash
# US job-intent: SMB filter → local email probe → Apify fallback → Smartlead CSV
# Usage: bash scripts/run_us_jobs_email_enrich.sh [date] [--no-apify]

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE="${1:-2026-07-02}"
USE_APIFY=1
if [[ "${2:-}" == "--no-apify" ]]; then
  USE_APIFY=0
fi

READY="$ROOT/exports/smartlead_ready_jobs_us_${DATE}.csv"
WEBSITES="$ROOT/exports/jobs_us_with_websites_${DATE}.csv"
SMB="$ROOT/exports/jobs_us_smb_${DATE}.csv"
EMAILS="$ROOT/exports/jobs_us_with_emails_${DATE}.csv"
EMAILS_APIFY="$ROOT/exports/jobs_us_with_emails_apify_${DATE}.csv"
IMPORT="$ROOT/exports/smartlead_us_import_${DATE}.csv"
LOG="$ROOT/exports/us_enrich_${DATE}.log"

if [[ ! -f "$READY" ]]; then
  echo "Missing $READY — run scrape import first." >&2
  exit 1
fi

export PYTHONUNBUFFERED=1
{
  echo "=== US jobs pipeline $(date) ==="

  if [[ ! -f "$WEBSITES" ]]; then
    echo "Step 1/5: Finding company websites..."
    python3 -u "$ROOT/scripts/find_company_websites.py" \
      "$READY" --out "$WEBSITES" --skip-recruiters --country US --delay 1.0
  else
    echo "Step 1/5: Websites already done: $WEBSITES"
  fi

  echo "Step 2/5: Filtering to SMB companies..."
  python3 "$ROOT/scripts/filter_smb_jobs_csv.py" "$WEBSITES" --out "$SMB"

  echo "Step 3/5: Local email probe on SMB list (see [ok]/[miss] lines)..."
  python3 -u "$ROOT/scripts/enrich_csv_emails_from_websites.py" \
    "$SMB" --out "$EMAILS" --delay 0.5 --timeout 15

  FINAL_EMAILS="$EMAILS"
  if [[ "$USE_APIFY" -eq 1 ]]; then
    echo "Step 4/5: Apify email fallback for rows still missing email..."
    if python3 "$ROOT/scripts/enrich_emails_apify.py" "$EMAILS" --out "$EMAILS_APIFY"; then
      FINAL_EMAILS="$EMAILS_APIFY"
    else
      echo "Apify step failed — continuing with local probe results only."
    fi
  else
    echo "Step 4/5: Skipping Apify (--no-apify)"
  fi

  echo "Step 5/5: Building Smartlead import file..."
  python3 "$ROOT/scripts/prepare_smartlead_jobs_import.py" "$FINAL_EMAILS" --out "$IMPORT"

  WITH_EMAIL=$(python3 -c "import csv; print(sum(1 for r in csv.DictReader(open('$IMPORT')) if (r.get('email') or '').strip()))")
  echo "=== Done $(date) ==="
  echo "SMB file: $SMB"
  echo "Emails file: $FINAL_EMAILS"
  echo "Smartlead import: $IMPORT ($WITH_EMAIL leads with email)"
} 2>&1 | tee -a "$LOG"
