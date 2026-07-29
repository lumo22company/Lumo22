#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
echo "=== Smartlead import (campaign 3521696) ==="
python3 scripts/prepare_smartlead_upload_csv.py \
  exports/smartlead_us_import_2026-07-02.csv \
  --out exports/smartlead_us_upload_2026-07-02.csv
echo ""
python3 scripts/import_smartlead_csv.py \
  exports/smartlead_us_import_2026-07-02.csv \
  --campaign-id 3521696
echo ""
echo "=== Done. Press Enter to close. ==="
read -r
