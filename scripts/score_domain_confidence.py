#!/usr/bin/env python3
"""
Split resolved company websites into "trust it" and "pay to verify".

find_company_websites.py always returns *a* domain, not necessarily the right one — it resolved
"bread & Butter" (a Chicago comms agency) to breadandbutterwines.com. A wrong domain is worse
than a miss: it yields a real email at the wrong company, and the opener ("Saw you're hiring for
a Social Media Manager at bread & Butter") then lands somewhere it makes no sense.

Scores how well the domain matches the company name so the free path keeps the confident
majority and scarce paid enrichment credits go only where they earn their keep.

Usage:
  python3 scripts/score_domain_confidence.py exports/companies_us_with_websites.csv \\
    --confident-out exports/companies_confident.csv \\
    --review-out exports/clay_import_needs_enrichment.csv --review-limit 200
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from urllib.parse import urlparse

NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Words that carry no identity — "Bright Cellars" and "Bright Cellars Inc" are the same firm,
# and matching on "the" or "group" would let almost anything through.
STOPWORDS = frozenset(
    {"the", "inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company",
     "group", "holdings", "agency", "studio", "studios", "media", "brands", "brand",
     "and", "of", "for", "plc", "gmbh"}
)


def slug(text: str) -> str:
    return NON_ALNUM.sub("", (text or "").lower())


def tokens(name: str) -> list[str]:
    parts = [p for p in NON_ALNUM.sub(" ", (name or "").lower()).split() if p]
    meaningful = [p for p in parts if p not in STOPWORDS and len(p) > 1]
    return meaningful or parts


def domain_labels(website: str) -> tuple[str, str]:
    """
    Return (registrable name, subdomain prefix).

    The organisation is the registrable second-level name, not the leftmost label:
    arcaea.lowiro.com belongs to lowiro, and "Arcaea" matching the subdomain means the company
    is a *product on someone else's site* — the opposite of a confident match.
      arcaea.lowiro.com -> ("lowiro", "arcaea")
      www.mandalascrubs.com -> ("mandalascrubs", "")
    """
    host = urlparse(website if "://" in (website or "") else f"https://{website}").hostname or ""
    host = host.lower().removeprefix("www.")
    if not host:
        return "", ""
    labels = host.split(".")
    # Strip the public suffix: .co.uk style needs two labels removed, .com one.
    if len(labels) >= 3 and labels[-2] in ("co", "com", "org", "net", "ac", "gov"):
        registrable_idx = len(labels) - 3
    elif len(labels) >= 2:
        registrable_idx = len(labels) - 2
    else:
        return slug(host), ""
    registrable = labels[registrable_idx] if registrable_idx >= 0 else ""
    prefix = "".join(labels[:registrable_idx]) if registrable_idx > 0 else ""
    return slug(registrable), slug(prefix)


def score(company: str, website: str) -> tuple[int, str]:
    """0-100 confidence that this domain belongs to this company."""
    if not (website or "").strip():
        return 0, "no_website"
    c_slug = slug(company)
    registrable, prefix = domain_labels(website)
    if not registrable:
        return 0, "unparseable"
    if not c_slug:
        return 0, "no_company"

    if c_slug == registrable:
        return 100, "exact"

    # Company name inside the registrable name. Extra characters mean a different organisation
    # that merely shares a prefix — breadandbutterwines is not bread & Butter.
    if c_slug in registrable:
        extra = len(registrable) - len(c_slug)
        if extra <= 3:
            return 90, "contained"
        if extra <= 6:
            return 55, "contained_with_tail"
        return 35, "contained_long_tail"

    # Domain shorter than the name (abbreviations: "ZAGG, Inc." -> zagg) is usually right.
    if registrable in c_slug and len(registrable) >= 4:
        return 80, "domain_in_company"

    # The name only matches a subdomain: the site belongs to someone else.
    if prefix and (c_slug == prefix or c_slug in prefix):
        return 40, "subdomain_only"

    toks = tokens(company)
    if toks:
        hits = sum(1 for t in toks if t in registrable)
        ratio = hits / len(toks)
        joined = "".join(toks)
        # All tokens present is only convincing when the domain is not padded with extra words.
        if ratio == 1.0:
            padding = len(registrable) - len(joined)
            if padding <= 3:
                return 85, "all_tokens"
            return 45, "all_tokens_padded"
        if ratio >= 0.6:
            return 50, "most_tokens"
        if hits and toks[0] in registrable:
            return 40, "first_token_only"
        if hits:
            return 25, "partial_token"
    return 15, "no_match"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--confident-out", type=Path, required=True)
    ap.add_argument("--review-out", type=Path, required=True)
    ap.add_argument("--threshold", type=int, default=70, help="Score at or above this is trusted")
    ap.add_argument("--review-limit", type=int, default=0, help="Cap the review file (e.g. your credit balance)")
    ap.add_argument("--company-col", default="company")
    ap.add_argument("--website-col", default="website")
    args = ap.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"No rows in {args.input_csv}")

    cols = list(rows[0].keys())
    scored = []
    for r in rows:
        s, why = score(r.get(args.company_col, ""), r.get(args.website_col, ""))
        r = dict(r)
        r["domain_confidence"] = str(s)
        r["domain_match"] = why
        scored.append(r)

    confident = [r for r in scored if int(r["domain_confidence"]) >= args.threshold]
    review = [r for r in scored if int(r["domain_confidence"]) < args.threshold]
    # Weakest first: those are the ones the free path is most likely to have got wrong.
    review.sort(key=lambda r: int(r["domain_confidence"]))
    if args.review_limit > 0:
        review = review[: args.review_limit]

    out_cols = cols + ["domain_confidence", "domain_match"]
    for path, data in ((args.confident_out, confident), (args.review_out, review)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    breakdown: dict[str, int] = {}
    for r in scored:
        breakdown[r["domain_match"]] = breakdown.get(r["domain_match"], 0) + 1

    print(f"scored: {len(scored)}")
    print(f"  confident (>={args.threshold}): {len(confident)}  -> {args.confident_out}")
    print(f"  needs enrichment (<{args.threshold}): {len(review)}  -> {args.review_out}")
    print("\nmatch types:")
    for why, n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
        print(f"  {why:<24} {n}")


if __name__ == "__main__":
    main()
