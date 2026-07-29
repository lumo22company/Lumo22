#!/usr/bin/env python3
"""Build a slim CSV for Smartlead UI import with correct merge field names."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for r in rows:
        email = (r.get("email") or "").strip()
        if not email:
            continue
        out_rows.append(
            {
                "email": email,
                "company_name": (r.get("business_name") or r.get("company") or "").strip(),
                "job_title": (r.get("job_title") or "").strip(),
                "personalization_line": (r.get("personalization_line") or "").strip(),
                "job_url": (r.get("job_url") or "").strip(),
                "website": (r.get("website") or "").strip(),
                "city": (r.get("city") or "").strip(),
            }
        )

    fields = ["email", "company_name", "job_title", "personalization_line", "job_url", "website", "city"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote {len(out_rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
