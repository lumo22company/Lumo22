#!/usr/bin/env python3
"""
Copy enrichment_best_email → email, keep rows with email, dedupe for Smartlead import.

  python scripts/prepare_smartlead_jobs_import.py exports/jobs_us_with_emails_2026-07-02.csv \\
    --out exports/smartlead_us_import_2026-07-02.csv
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--drop-wix-sentry", action="store_true", default=True)
    args = ap.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty csv: {args.input_csv}")
    fields = list(rows[0].keys())

    staged = args.out.with_suffix(".staged.csv")
    for r in rows:
        if not (r.get("email") or "").strip():
            r["email"] = (r.get("enrichment_best_email") or "").strip()

    with_email = [r for r in rows if (r.get("email") or "").strip()]
    if not with_email:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
        staged.unlink(missing_ok=True)
        print(f"Input rows: {len(rows)} | with email: 0 | import file: {args.out} (header only)")
        raise SystemExit(
            "No rows with email — fix Apify token (HTTP 401) or run local email probe first."
        )

    with staged.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(with_email)

    dedupe_script = Path(__file__).resolve().parent / "dedupe_smartlead_csv.py"
    cmd = [sys.executable, str(dedupe_script), str(staged), "--out", str(args.out)]
    if args.drop_wix_sentry:
        cmd.append("--drop-wix-sentry")
    subprocess.run(cmd, check=True)
    staged.unlink(missing_ok=True)

    print(f"Input rows: {len(rows)} | with email: {len(with_email)} | import file: {args.out}")


if __name__ == "__main__":
    main()
