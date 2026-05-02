#!/usr/bin/env python3
"""
Shorten Google Maps-style business titles for outreach CSVs.

Default rule (middle ground): if the title contains ' - ', keep the full title unless
the part after the first ' - ' is long (>50 chars) or looks like an SEO/tagline fragment
('in Bristol', ', UK', 'Official Hyrox', etc.). Then keep only the left segment.

Re-run on Smartlead-ready CSVs to refresh business_name + personalization_line.

Example:
  python scripts/shorten_google_maps_business_titles.py \\
    exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_with_email_only.csv \\
    --city-col city \\
    --personalization-template 'Helping {name} in {city} turn local searches into more trial bookings and fuller classes.'
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

# Strip right-hand segment only when it looks like Maps SEO / location stuffing,
# OR when it is very long. Do NOT include generic "personal training" alone — that
# removes legitimate short descriptors (e.g. Gymset - Personal Training & ...).
SEO_HINTS = (
    "official",
    "hyrox",
    "crossfit gym",
    "in bristol",
    ", uk",
    "united kingdom",
    "gym and",
    "training club",
    "gym &",
)


def shorten_maps_title(title: str, max_right: int = 50) -> str:
    t = (title or "").strip().strip('"').strip()
    t = re.sub(r",\s*UK\s*$", "", t, flags=re.I).strip()
    if " - " not in t:
        return t
    left, right = t.split(" - ", 1)
    left, right = left.strip(), right.strip()
    rlow = right.lower()
    if len(right) > max_right:
        return left
    if any(h in rlow for h in SEO_HINTS):
        return left
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", help="CSV to rewrite in place")
    ap.add_argument("--city-col", default="city", help="Column for city in personalization")
    ap.add_argument(
        "--name-col",
        default="business_name",
        help="Column holding Maps / business title",
    )
    ap.add_argument(
        "--personalization-template",
        default=(
            "Helping {name} in {city} turn local searches into more trial bookings "
            "and fuller classes."
        ),
        help="Use {name} and {city} placeholders",
    )
    args = ap.parse_args()

    path = Path(args.csv_path)
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No rows; nothing to do.")
        return
    fields = list(rows[0].keys())

    for r in rows:
        raw = r.get(args.name_col, "")
        short = shorten_maps_title(raw)
        r[args.name_col] = short
        city = (r.get(args.city_col) or "").strip() or "Bristol"
        if "personalization_line" in fields:
            r["personalization_line"] = args.personalization_template.format(
                name=short, city=city
            )

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Updated {len(rows)} rows in {path}")


if __name__ == "__main__":
    main()
