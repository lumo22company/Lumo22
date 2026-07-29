#!/usr/bin/env python3
"""
Drop companies that can never buy, before spending enrichment credits on them.

filter_smb_jobs_csv.py already knows which names are staffing agencies and enterprises, but it
needs a resolved website to run — and resolving websites is the expensive step. So on a fresh
scrape it can only filter *after* you have already paid to enrich the junk.

This runs the same name-based rules with no website required, so agencies, household-name
enterprises and unnamed employers are gone before Clay/Hunter ever sees them. Domain-dependent
checks stay in filter_smb_jobs_csv.py; run that afterwards, once enrichment has supplied domains.

Usage:
  python3 scripts/filter_junk_companies.py exports/companies_us_2026-07-29.csv \\
    --out exports/companies_us_2026-07-29_clean.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Single source of truth: reuse the lists the SMB filter already maintains rather than keeping
# a second copy that drifts out of sync.
from filter_smb_jobs_csv import ENTERPRISE_NAMES, RECRUITER_HINT  # noqa: E402

# Employers with no identifiable name — nothing to enrich, nothing to address.
ANONYMOUS = frozenset(
    {
        "confidential",
        "confidential company",
        "undisclosed",
        "private company",
        "company confidential",
        "n/a",
        "unknown",
    }
)

# Job boards and aggregators sometimes appear as the "company" on syndicated listings.
# Split by ambiguity: these names are distinctive enough that a substring match is safe.
BOARD_HINT = re.compile(
    r"\b(ziprecruiter|glassdoor|careerbuilder|talentify|get\.it|jobs via|snagajob)\b",
    re.I,
)

# These double as ordinary English words or brand fragments — "3Headed Monster" is a creative
# agency, "Indeed Brewing Company" is a brewery. Substring matching drops real prospects, so
# they only count when they are the entire company name (or an obvious domain).
BOARD_EXACT = frozenset({"linkedin", "indeed", "monster", "jobot", "lensa", "ladders"})


def classify(company: str) -> tuple[bool, str]:
    """Return (keep, reason_if_dropped)."""
    name = (company or "").strip()
    if not name:
        return False, "no_company_name"
    folded = name.casefold()
    if folded in ANONYMOUS:
        return False, "anonymous_employer"
    if BOARD_HINT.search(name):
        return False, "job_board_or_aggregator"
    bare = re.sub(r"\.(com|io|co\.uk)$", "", folded).strip()
    if bare in BOARD_EXACT:
        return False, "job_board_or_aggregator"
    if RECRUITER_HINT.search(name):
        return False, "staffing_agency"
    if folded in ENTERPRISE_NAMES:
        return False, "enterprise"
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rejects", type=Path, default=None, help="Optional CSV of dropped rows")
    ap.add_argument(
        "--company-column",
        default="",
        help="Override company column (default: auto-detect)",
    )
    args = ap.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"No rows in {args.input_csv}")

    cols = list(rows[0].keys())
    company_col = args.company_column or next(
        (c for c in ("company", "business_name", "company_name") if c in cols), ""
    )
    if not company_col:
        raise SystemExit(f"No company column found in {cols}")

    kept: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    reasons: Counter = Counter()
    for r in rows:
        keep, reason = classify(r.get(company_col, ""))
        if keep:
            kept.append(r)
        else:
            reasons[reason] += 1
            d = dict(r)
            d["_drop_reason"] = reason
            dropped.append(d)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(kept)

    if args.rejects and dropped:
        with args.rejects.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols + ["_drop_reason"], extrasaction="ignore")
            w.writeheader()
            w.writerows(dropped)

    print(f"in:   {len(rows)}")
    print(f"kept: {len(kept)}")
    print(f"drop: {len(dropped)}")
    for reason, n in reasons.most_common():
        print(f"        {reason:<26} {n}")
    print(f"\nWrote {args.out}")
    if args.rejects and dropped:
        print(f"Rejects (check for false drops): {args.rejects}")


if __name__ == "__main__":
    main()
