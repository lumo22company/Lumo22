#!/usr/bin/env python3
"""
Resolve company websites for job-lead CSVs without Apify or paid APIs.

Strategy (in order):
  1. Keep existing non-empty website values
  2. DuckDuckGo HTML search: "{company} official website UK"
  3. Domain slug guesses (.co.uk, .com) verified with a lightweight HTTP GET

Pair with enrich_csv_emails_from_websites.py to pull public emails from home/contact pages.

Example:
  python scripts/find_company_websites.py exports/smartlead_ready_jobs_smm_intent_2026-06-18.csv \\
    --out exports/jobs_with_websites_2026-06-18.csv --company-col company
  python scripts/enrich_csv_emails_from_websites.py exports/jobs_with_websites_2026-06-18.csv \\
    --out exports/jobs_with_emails_2026-06-18.csv --delay 0.35
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

RECRUITER_HINT = re.compile(
    r"\b(recruitment|recruiting|staffing|talent|resourc|executive search|employment agency)\b",
    re.I,
)
SUFFIX_DROP = re.compile(r"\b(ltd|limited|llc|inc|plc|llp|group|uk|the|and|co)\b", re.I)
BLOCKED_HOSTS = (
    "reed.co.uk",
    "indeed.",
    "linkedin.",
    "facebook.",
    "glassdoor.",
    "google.",
    "wikipedia.org",
    "find-and-update.company-information.service.gov.uk",
    "companieshouse.gov.uk",
    "youtube.com",
    "instagram.com",
    "twitter.com",
    "x.com",
)


def _norm_header(name: str) -> str:
    k = (name or "").lstrip("\ufeff").strip()
    if k.startswith('"') and k.endswith('"') and len(k) >= 2:
        k = k[1:-1]
    return k.strip()


def _slug(name: str) -> str:
    n = SUFFIX_DROP.sub("", name.lower())
    return re.sub(r"[^a-z0-9]+", "", n)[:48]


def _host_ok(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return not any(b in host for b in BLOCKED_HOSTS)


def _verify_url(session: requests.Session, url: str, timeout: int) -> bool:
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code < 400 and len(r.content) > 200
    except Exception:
        return False


def _ddg_website(session: requests.Session, company: str, timeout: int, *, country: str = "GB") -> str:
    region = "US" if country.upper() == "US" else "UK"
    kl = "us-en" if country.upper() == "US" else "uk-en"
    query = f"{company} official website {region}"
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            r = session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": "", "kl": kl},
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code >= 400:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.result__a"):
                href = a.get("href", "")
                if "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    if m:
                        href = unquote(m.group(1))
                if href.startswith("http") and _host_ok(href):
                    return href
            return ""
        except Exception as e:
            last_err = e
            if attempt < 3:
                time.sleep(2.0 * attempt)
    if last_err:
        print(f"[ddg] failed for {company[:40]!r}: {last_err}", flush=True)
    return ""


def _guess_domains(company: str) -> list[str]:
    slug = _slug(company)
    if len(slug) < 4:
        return []
    candidates = [
        f"https://www.{slug}.co.uk",
        f"https://{slug}.co.uk",
        f"https://www.{slug}.com",
        f"https://{slug}.com",
    ]
    # also try first word only for long names
    parts = re.findall(r"[a-z0-9]{4,}", _slug(company))
    if parts and parts[0] != slug:
        candidates.extend([f"https://www.{parts[0]}.co.uk", f"https://www.{parts[0]}.com"])
    out: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def resolve_website(
    session: requests.Session,
    company: str,
    *,
    timeout: int,
    skip_recruiters: bool,
    country: str = "GB",
) -> tuple[str, str]:
    company = (company or "").strip()
    if not company:
        return "", "empty_company"
    if skip_recruiters and RECRUITER_HINT.search(company):
        return "", "skipped_recruiter"

    url = _ddg_website(session, company, timeout, country=country)
    if url:
        return url, "duckduckgo"

    for candidate in _guess_domains(company):
        if _verify_url(session, candidate, timeout):
            return candidate, "domain_guess"
    return "", "not_found"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--company-col", default="company")
    ap.add_argument("--website-col", default="website")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between lookups")
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--skip-recruiters", action="store_true", help="Skip obvious recruitment agencies")
    ap.add_argument("--country", choices=("GB", "US"), default="GB", help="DuckDuckGo region for website lookup")
    ap.add_argument("--force", action="store_true", help="Re-resolve even when website is already set")
    args = ap.parse_args()

    with open(args.input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [{_norm_header(k): v for k, v in row.items()} for row in reader]
        fieldnames = [_norm_header(h) for h in (reader.fieldnames or [])]

    if args.website_col not in fieldnames:
        fieldnames.append(args.website_col)
    if "website_source" not in fieldnames:
        fieldnames.append("website_source")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; Lumo22WebsiteFinder/1.0)"})

    todo = [r for r in rows if args.force or not (r.get(args.website_col) or "").strip()]
    if args.limit > 0:
        todo = todo[: args.limit]

    resolved = 0
    for i, row in enumerate(rows):
        if (row.get(args.website_col) or "").strip() and not args.force:
            row.setdefault("website_source", "existing")
            continue
        if row not in todo:
            continue
        company = (row.get(args.company_col) or row.get("business_name") or "").strip()
        url, source = resolve_website(
            session,
            company,
            timeout=args.timeout,
            skip_recruiters=args.skip_recruiters,
            country=args.country,
        )
        if url:
            row[args.website_col] = url
            row["website_source"] = source
            resolved += 1
            print(f"[ok] {company} -> {url} ({source})")
        else:
            row["website_source"] = source
            print(f"[miss] {company} ({source})")
        if args.delay > 0:
            time.sleep(args.delay)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    have_site = sum(1 for r in rows if (r.get(args.website_col) or "").strip())
    print(f"Wrote {args.out} | websites={have_site}/{len(rows)} | newly_resolved={resolved}")


if __name__ == "__main__":
    main()
