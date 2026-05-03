#!/usr/bin/env python3
"""
Deduplicate Smartlead CSV rows by email (first row wins, case-insensitive).

Optional: drop rows whose email matches junk patterns (e.g. Wix Sentry).

  python scripts/dedupe_smartlead_csv.py in.csv --out out.csv
  python scripts/dedupe_smartlead_csv.py in.csv --out out.csv --drop-wix-sentry
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--drop-wix-sentry",
        action="store_true",
        help="Skip rows with @sentry.wixpress.com or @sentry-next.wixpress.com",
    )
    args = ap.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("empty csv")
    fields = list(rows[0].keys())

    seen: set[str] = set()
    out_rows: list[dict] = []
    skipped_dup = 0
    skipped_sentry = 0
    for r in rows:
        email = (r.get("email") or "").strip()
        if not email:
            continue
        el = email.casefold()
        if args.drop_wix_sentry and (
            "@sentry.wixpress.com" in el or "@sentry-next.wixpress.com" in el
        ):
            skipped_sentry += 1
            continue
        if el in seen:
            skipped_dup += 1
            continue
        seen.add(el)
        out_rows.append(r)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    print(
        f"Wrote {len(out_rows)} rows to {args.out} "
        f"(skipped {skipped_dup} duplicate emails, {skipped_sentry} Wix sentry rows)"
    )


if __name__ == "__main__":
    main()
