#!/usr/bin/env bash
# Force caption PDF generation + email for one order (same as CAPTIONS_FORCE_DELIVER_NOW.md).
#
# Usage:
#   export BASE_URL=https://www.lumo22.com
#   export CAPTIONS_DELIVER_TEST_SECRET='paste-from-railway'
#   export INTAKE_TOKEN='paste-from-captions-intake-url'
#   ./scripts/force_caption_delivery.sh
#
#   ./scripts/force_caption_delivery.sh --background   # don't wait for AI
#
# Or put BASE_URL + secrets in .env (this script loads .env from project root).
# Add CAPTIONS_DELIVER_TEST_SECRET in Railway → Variables, redeploy, then run.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

SYNC=1
if [[ "${1:-}" == "--background" ]] || [[ "${1:-}" == "-b" ]]; then
  SYNC=0
fi

BASE_URL="${BASE_URL:-}"
BASE_URL="${BASE_URL%/}"
if [[ -z "$BASE_URL" ]]; then
  echo "Set BASE_URL (e.g. export BASE_URL=https://www.lumo22.com)"
  exit 1
fi
if [[ ! "$BASE_URL" =~ ^https?:// ]]; then
  BASE_URL="https://${BASE_URL}"
fi

SECRET="${CAPTIONS_DELIVER_TEST_SECRET:-}"
TOKEN="${INTAKE_TOKEN:-}"

if [[ -z "$SECRET" ]]; then
  read -r -s -p "CAPTIONS_DELIVER_TEST_SECRET: " SECRET
  echo
fi
if [[ -z "$TOKEN" ]]; then
  read -r -p "Intake token (from ?t= in form URL): " TOKEN
fi

if [[ -z "$SECRET" || -z "$TOKEN" ]]; then
  echo "Need CAPTIONS_DELIVER_TEST_SECRET and INTAKE_TOKEN."
  exit 1
fi

ENC_TOKEN=$(INTAKE_TOKEN="$TOKEN" python3 -c "import os, urllib.parse; print(urllib.parse.quote(os.environ['INTAKE_TOKEN'], safe=''))")
ENC_SECRET=$(CAPTIONS_DELIVER_TEST_SECRET="$SECRET" python3 -c "import os, urllib.parse; print(urllib.parse.quote(os.environ['CAPTIONS_DELIVER_TEST_SECRET'], safe=''))")
URL="${BASE_URL}/api/captions-deliver-test?t=${ENC_TOKEN}&secret=${ENC_SECRET}"

if [[ "$SYNC" == 1 ]]; then
  URL="${URL}&sync=1"
  echo "Calling ${BASE_URL}/api/captions-deliver-test (sync=1, up to ~5 min)…"
  curl -sS -m 320 "$URL"
  echo
else
  echo "Calling (background)…"
  curl -sS -m 60 "$URL"
  echo
fi

echo "Done. Check inbox/spam and Railway logs for [Captions] / [SendGrid]."
