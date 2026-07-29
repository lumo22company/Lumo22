#!/usr/bin/env python3
"""
Keep SMB-sized hiring companies; drop Fortune 500, staffing agencies, and junk URLs.

  python scripts/filter_smb_jobs_csv.py exports/jobs_us_with_websites_2026-07-02.csv \\
    --out exports/jobs_us_smb_2026-07-02.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from urllib.parse import urlparse

RECRUITER_HINT = re.compile(
    r"\b(recruitment|recruiting|staffing|talent agency|executive search|"
    r"employment agency|creative circle|robert half|insight global|aquent|"
    r"hackajob|grail talent|24 seven|careerscape)\b",
    re.I,
)

ENTERPRISE_NAMES = frozenset(
    n.casefold()
    for n in (
        "Amazon",
        "Amazon Web Services (AWS)",
        "USAA",
        "Waymo",
        "Google",
        "Meta",
        "Facebook",
        "Apple",
        "Microsoft",
        "Walmart",
        "Target",
        "Capital One",
        "JCPenney",
        "Hilton",
        "Hyatt",
        "Snap Inc.",
        "TikTok",
        "Twilio",
        "FanDuel",
        "Hasbro",
        "Instacart",
        "Procter & Gamble",
        "Lenovo",
        "Compass Group USA",
        "D.R. Horton",
        "Darden",
        "DLA Piper",
        "Proskauer Rose LLP",
        "The State University of New York",
        "MrBeast",
        "OpenAI",
        "ChatGPT Jobs",
        "Perplexity",
        "FleishmanHillard",
        "Razorfish",
        "Turnitin",
        "Realtor.com",
    )
)

ENTERPRISE_DOMAIN_HINTS = (
    "amazon.com",
    "aws.amazon.com",
    "usaa.com",
    "waymo.com",
    "google.com",
    "facebook.com",
    "meta.com",
    "apple.com",
    "microsoft.com",
    "walmart.com",
    "capitalone.com",
    "jcpenney.com",
    "hilton.com",
    "hyatt.com",
    "snap.com",
    "tiktok.com",
    "twilio.com",
    "fanduel.com",
    "hasbro.com",
    "instacart.com",
    "pg.com",
    "lenovo.com",
    "compass-usa.com",
    "drhorton.com",
    "darden.com",
    "openai.com",
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
)


def _host(url: str) -> str:
    try:
        h = urlparse((url or "").strip()).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def is_smb_row(row: dict[str, str]) -> tuple[bool, str]:
    company = (row.get("business_name") or row.get("company") or "").strip()
    website = (row.get("website") or "").strip()
    if not website:
        return False, "no_website"
    host = _host(website)
    if not host:
        return False, "bad_website"
    if any(h in host for h in ENTERPRISE_DOMAIN_HINTS):
        return False, "enterprise_domain"
    if company.casefold() in ENTERPRISE_NAMES:
        return False, "enterprise_name"
    if RECRUITER_HINT.search(company):
        return False, "staffing_agency"
    return True, "ok"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    kept: list[dict[str, str]] = []
    reasons: dict[str, int] = {}
    for row in rows:
        ok, reason = is_smb_row(row)
        reasons[reason] = reasons.get(reason, 0) + 1
        if ok:
            kept.append(row)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)

    print(f"Wrote {len(kept)}/{len(rows)} SMB rows to {args.out}")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
