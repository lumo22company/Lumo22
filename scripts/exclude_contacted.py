#!/usr/bin/env python3
"""
Remove leads already sent to Smartlead, before spending enrichment credits on them.

Fresh scrapes re-find companies from previous batches — measured at 140 of 609 (23%) on the
July US runs. Re-importing them means paying to enrich a known contact and then emailing a
person who has already had the sequence: wasted credits, and spam complaints against a sending
domain whose reputation is already the suspect part of this funnel.

Builds the contacted set from every Smartlead import/upload CSV in exports/ plus the
seen_leads_registry, matching on normalized company name and on email.

Usage:
  python3 scripts/exclude_contacted.py exports/companies_us_combined_clean.csv \\
    --out exports/companies_us_new_only.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from dedupe_jobs_by_company import normalize_company  # noqa: E402

# Every file Smartlead has ever been fed from this repo.
CONTACTED_GLOBS = (
    "exports/smartlead_us_import_*.csv",
    "exports/smartlead_us_upload_*.csv",
    "exports/smartlead_new_only_*.csv",
    "exports/SMARTLEAD_IMPORT_*.csv",
    "exports/smartlead_ready_*.csv",
)
COMPANY_COLS = ("company_name", "company", "business_name")


def _read(path: str) -> list[dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def build_contacted(globs=CONTACTED_GLOBS, include_ready: bool = False) -> tuple[set[str], set[str]]:
    """
    Returns (company_keys, emails).

    smartlead_ready_* files are the pre-enrichment stage — rows in them were candidates, not
    necessarily sends — so they are excluded by default to avoid suppressing leads that were
    never actually emailed.
    """
    companies: set[str] = set()
    emails: set[str] = set()
    for pattern in globs:
        if not include_ready and "smartlead_ready_" in pattern:
            continue
        for path in glob.glob(str(ROOT / pattern)):
            for row in _read(path):
                email = (row.get("email") or "").strip().lower()
                # Only a row that carried an address could have been sent.
                if not email or "@" not in email:
                    continue
                emails.add(email)
                for col in COMPANY_COLS:
                    v = (row.get(col) or "").strip()
                    if v:
                        key = normalize_company(v)
                        if key:
                            companies.add(key)
                        break
    return companies, emails


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--excluded-out", type=Path, default=None)
    ap.add_argument("--company-col", default="company")
    ap.add_argument(
        "--include-ready",
        action="store_true",
        help="Also treat smartlead_ready_* candidates as contacted (more aggressive)",
    )
    args = ap.parse_args()

    companies, emails = build_contacted(include_ready=args.include_ready)
    print(f"contacted set: {len(companies)} companies, {len(emails)} emails")

    rows = _read(str(args.input_csv))
    if not rows:
        raise SystemExit(f"No rows in {args.input_csv}")

    kept, dropped = [], []
    for r in rows:
        key = normalize_company(r.get(args.company_col, ""))
        email = (r.get("email") or "").strip().lower()
        if (key and key in companies) or (email and email in emails):
            d = dict(r)
            d["_excluded_reason"] = "company_already_contacted" if key in companies else "email_already_contacted"
            dropped.append(d)
        else:
            kept.append(r)

    cols = list(rows[0].keys())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)

    if args.excluded_out and dropped:
        with args.excluded_out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols + ["_excluded_reason"], extrasaction="ignore")
            w.writeheader()
            w.writerows(dropped)

    print(f"in:       {len(rows)}")
    print(f"new:      {len(kept)}")
    print(f"excluded: {len(dropped)} already contacted")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
