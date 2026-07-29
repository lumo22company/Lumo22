#!/usr/bin/env python3
"""
Collapse job-posting rows to one row per company, ready for enrichment (Clay / Hunter / Apollo).

Job scrapes return one row per posting, so a company hiring three roles appears three times.
Left alone that costs an enrichment credit per duplicate and, worse, sends the same person the
same sequence three times.

Which posting survives matters, because the personalization line is built from its job title
("Saw you're hiring for a Social Media Manager role at X"). Rows are ranked by how close the
title sits to what we actually sell — a social/content hire is a far stronger opening than a
generic marketing one — then by seniority as a tie-break.

Usage:
  python3 scripts/dedupe_jobs_by_company.py exports/smartlead_ready_jobs_us_2026-07-29.csv \\
    --out exports/companies_us_2026-07-29.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

# Closest to what we sell first. A company hiring a "Social Media Manager" is advertising
# exactly the job our product does; "Marketing Assistant" is a much weaker hook.
TITLE_TIERS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (100, ("social media", "instagram", "tiktok", "paid social")),
    (80, ("content creator", "content marketing", "content strategist", "social")),
    (60, ("community manager", "influencer", "brand content")),
    (40, ("digital marketing", "brand marketing", "content")),
    (20, ("marketing coordinator", "growth marketing", "email marketing")),
)

# Tie-break within the same tier: a manager owns budget, an assistant does not.
SENIORITY = (
    (30, ("head of", "director", "vp ", "chief")),
    (25, ("manager", "lead")),
    (15, ("strategist", "specialist")),
    (10, ("coordinator",)),
    (5, ("assistant", "intern", "junior")),
)

LEGAL_SUFFIXES = re.compile(
    r"\b(inc|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|plc|gmbh|group|holdings)\b\.?",
    re.I,
)
NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_company(name: str) -> str:
    """
    Match 'bread & Butter', 'Bread and Butter LLC' and 'BREAD & BUTTER, Inc.' to one key.
    Deliberately conservative: two genuinely different firms sharing a short name is rarer
    than one firm written three ways, but we keep enough of the name to avoid over-merging.
    """
    s = (name or "").strip().lower()
    if not s:
        return ""
    s = s.replace("&", " and ")
    s = LEGAL_SUFFIXES.sub(" ", s)
    s = NON_ALNUM.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s


def title_score(title: str) -> int:
    t = (title or "").strip().lower()
    if not t:
        return 0
    score = 0
    for points, needles in TITLE_TIERS:
        if any(n in t for n in needles):
            score = points
            break
    for points, needles in SENIORITY:
        if any(n in t for n in needles):
            score += points
            break
    return score


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--company-column",
        default="",
        help="Override company column (default: auto-detect company / business_name / company_name)",
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

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    unnamed = 0
    for r in rows:
        key = normalize_company(r.get(company_col, ""))
        if not key:
            unnamed += 1
            continue
        groups[key].append(r)

    out_rows: list[dict[str, str]] = []
    for key, group in groups.items():
        # Highest product-relevance wins; stable so equal scores keep source order.
        best = max(group, key=lambda r: title_score(r.get("job_title", "")))
        row = dict(best)
        row["duplicate_postings"] = str(len(group))
        titles = []
        for r in group:
            t = (r.get("job_title") or "").strip()
            if t and t not in titles:
                titles.append(t)
        row["all_job_titles"] = " | ".join(titles)
        out_rows.append(row)

    out_fields = cols + ["duplicate_postings", "all_job_titles"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    multi = sum(1 for r in out_rows if int(r["duplicate_postings"]) > 1)
    print(f"in:  {len(rows)} postings")
    print(f"out: {len(out_rows)} companies  ({len(rows) - len(out_rows)} duplicate postings collapsed)")
    print(f"     {multi} companies were hiring more than one relevant role")
    if unnamed:
        print(f"     {unnamed} rows dropped (no company name)")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
