#!/usr/bin/env python3
"""
Scrape high-intent hiring leads (social media / content roles) from public job boards.

Primary path: Apify jobs actor (Indeed + LinkedIn) when account has quota.
Fallback: Reed.co.uk HTML + Arbeitnow API (no Apify required).

Outputs under exports/:
  jobs_raw_smm_intent_{date}.csv
  smartlead_ready_jobs_smm_intent_{date}.csv
  smartlead_new_only_jobs_smm_intent_{date}.csv  (rows with email only)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"
APIFY_JOBS_ACTOR = "cNTtg2vu14kVfToO6"

REED_SEARCHES = [
    ("https://www.reed.co.uk/jobs/social-media-manager-jobs", "United Kingdom", "social media manager"),
    ("https://www.reed.co.uk/jobs/social-media-jobs-in-london", "London, UK", "social media london"),
    ("https://www.reed.co.uk/jobs/content-creator-jobs", "United Kingdom", "content creator"),
    ("https://www.reed.co.uk/jobs/digital-marketing-jobs", "United Kingdom", "digital marketing"),
    ("https://www.reed.co.uk/jobs/marketing-jobs-in-bristol", "Bristol, UK", "marketing bristol"),
    ("https://www.reed.co.uk/jobs/marketing-jobs-in-manchester", "Manchester, UK", "marketing manchester"),
]

APIFY_QUERIES_UK = [
    ("social media manager", "United Kingdom"),
    ("instagram content creator", "United Kingdom"),
    ("part time social media", "United Kingdom"),
]

# Broad US coverage for volume — each run can return up to --apify-max-results (actor max 1000).
APIFY_QUERIES_US = [
    ("social media manager", "United States"),
    ("content creator", "United States"),
    ("instagram manager", "United States"),
    ("tiktok content creator", "United States"),
    ("digital marketing coordinator", "United States"),
    ("community manager", "United States"),
    ("social media specialist", "United States"),
    ("marketing coordinator", "United States"),
    ("brand content creator", "United States"),
    ("social media manager", "New York, NY"),
    ("social media manager", "Los Angeles, CA"),
    ("social media manager", "Chicago, IL"),
    ("social media manager", "Miami, FL"),
    ("social media manager", "Austin, TX"),
    ("social media manager", "Dallas, TX"),
    ("content creator", "Atlanta, GA"),
    ("digital marketing", "Seattle, WA"),
    ("social media", "Phoenix, AZ"),
    ("social media manager", "Remote"),
]

APIFY_QUERIES = APIFY_QUERIES_UK + [("social media manager", "United States")]

# --- Matrix mode -------------------------------------------------------------------------
# Job boards cap results per search, so a handful of nationwide queries plateaus early: the
# 2026-07-17 run used 9 searches and returned 372 rows. Volume comes from many narrow searches
# instead — every (title, metro) pair is its own capped result set, so the ceiling multiplies.
# 20 titles x 18 metros = 360 searches. Use --matrix, and --max-searches to stay inside Apify
# budget.
US_TITLES = [
    "social media manager",
    "social media coordinator",
    "social media specialist",
    "social media strategist",
    "content creator",
    "brand content creator",
    "digital content creator",
    "content strategist",
    "community manager",
    "instagram manager",
    "tiktok content creator",
    "paid social manager",
    "influencer marketing manager",
    "digital marketing coordinator",
    "marketing coordinator",
    "brand marketing manager",
    "growth marketing manager",
    "email marketing coordinator",
    "marketing assistant",
    "content marketing manager",
]

US_METROS = [
    "New York, NY",
    "Los Angeles, CA",
    "Chicago, IL",
    "Miami, FL",
    "Austin, TX",
    "Dallas, TX",
    "Houston, TX",
    "Atlanta, GA",
    "Seattle, WA",
    "Phoenix, AZ",
    "Denver, CO",
    "Boston, MA",
    "San Diego, CA",
    "Nashville, TN",
    "Charlotte, NC",
    "Philadelphia, PA",
    "Portland, OR",
    "Remote",
]


def build_matrix(titles: list[str], metros: list[str], max_searches: int = 0) -> list[tuple[str, str]]:
    """
    (title, metro) pairs, interleaved by metro so a truncated run still spans the whole country
    rather than exhausting every title in New York first.
    """
    pairs: list[tuple[str, str]] = []
    for m_i, metro in enumerate(metros):
        for t_i, title in enumerate(titles):
            pairs.append((t_i, m_i, title, metro))
    pairs.sort(key=lambda p: (p[0] + p[1], p[1]))
    out = [(t, m) for _, _, t, m in pairs]
    return out[:max_searches] if max_searches > 0 else out

US_LOCATION_HINT = re.compile(
    r"\b(United States|USA|U\.S\.|Remote|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|"
    r"MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|"
    r"New York|Los Angeles|Chicago|Miami|Austin|Dallas|Atlanta|Seattle|Phoenix|San Francisco|Boston|"
    r"Denver|Houston|Philadelphia|San Diego)\b",
    re.I,
)

NON_US_LOCATION_HINT = re.compile(
    r"\b(India|United Kingdom|UK\b|Dubai|UAE|Abu Dhabi|Australia|Canada|Germany|France|"
    r"Mumbai|Bangalore|Bengaluru|Delhi|Hyderabad|Chennai|Pune|Singapore|Philippines|"
    r"Mexico|Brazil|Spain|Italy|Netherlands|Ireland)\b",
    re.I,
)

INCLUDE = re.compile(
    r"social media|instagram|content creator|community manager|tiktok|copywriter|"
    r"marketing assistant|digital marketing|beauty|salon|aesthetic|spa",
    re.I,
)
EXCLUDE = re.compile(
    r"head of marketing|director|chief |vp |senior software|java engineer|kotlin|nurse|warehouse|driver",
    re.I,
)
SUFFIX_DROP = re.compile(r"\b(ltd|limited|llc|inc|plc|group|uk|the)\b", re.I)

FIELDNAMES = [
    "job_title",
    "company",
    "business_name",
    "location",
    "search_query",
    "job_url",
    "description",
    "source",
    "email",
    "website",
    "personalization_line",
    "city",
    "niche",
]


def _personalization(job_title: str, company: str) -> str:
    title = (job_title or "social media role").strip()
    co = (company or "").strip()
    if co and co != title:
        return (
            f"Saw you're hiring for a {title} role at {co} — thought I'd reach out "
            f"before you commit to a full hire."
        )
    return f"Saw you're hiring for a {title} — thought I'd reach out before you commit to a full hire."


def _to_row(raw: dict[str, str]) -> dict[str, str]:
    title = (raw.get("job_title") or "").strip()
    company = (raw.get("company") or "").strip() or title
    return {
        **raw,
        "business_name": company,
        "city": raw.get("location", ""),
        "niche": "hiring_smm",
        "email": raw.get("email", ""),
        "website": raw.get("website", ""),
        "personalization_line": _personalization(title, company),
    }


def _parse_reed(url: str, location: str, query: str, headers: dict[str, str]) -> list[dict[str, str]]:
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jobs: list[dict[str, str]] = []
    for art in soup.select("article"):
        title_el = art.select_one("h2 a") or art.select_one("h3 a")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        href = title_el.get("href", "")
        if not href.startswith("http"):
            href = "https://www.reed.co.uk" + href
        company = ""
        comp_el = art.select_one('[data-qa="job-card-company-name"]')
        if comp_el:
            company = comp_el.get_text(" ", strip=True)
        loc_el = art.select_one('[data-qa="job-card-location"]')
        loc = loc_el.get_text(" ", strip=True) if loc_el else location
        jobs.append(
            {
                "job_title": title,
                "company": company,
                "location": loc,
                "job_url": href,
                "search_query": query,
                "description": "",
                "source": "reed_uk",
            }
        )
    return jobs


def _fetch_arbeitnow(max_pages: int, headers: dict[str, str]) -> list[dict[str, str]]:
    jobs: list[dict] = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    for _ in range(max_pages):
        d = requests.get(url, headers=headers, timeout=30).json()
        jobs.extend(d.get("data", []))
        next_url = (d.get("links") or {}).get("next")
        if not next_url:
            break
        url = next_url
        time.sleep(0.5)
    pat = re.compile(
        r"social media|instagram|content creator|community manager|digital marketing|marketing generalist",
        re.I,
    )
    out: list[dict[str, str]] = []
    for j in jobs:
        blob = f"{j.get('title', '')} {j.get('description', '')}"
        if not pat.search(blob):
            continue
        out.append(
            {
                "job_title": (j.get("title") or "").strip(),
                "company": (j.get("company_name") or "").strip(),
                "location": (j.get("location") or "Remote/EU").strip(),
                "job_url": (j.get("url") or "").strip(),
                "search_query": "arbeitnow_board",
                "description": (j.get("description") or "")[:800],
                "source": "arbeitnow",
            }
        )
    return out


def _first_str(item: dict, *keys: str) -> str:
    for key in keys:
        val = item.get(key)
        if val is None:
            continue
        if isinstance(val, str):
            s = val.strip()
        elif isinstance(val, dict):
            s = _first_str(val, "name", "title", "text", "value")
        else:
            s = str(val).strip()
        if s:
            return s
    return ""


def _apify_item_to_row(item: dict, search_query: str, fallback_location: str) -> dict[str, str]:
    """Map khadinakbar/jobs-scraper (and similar) dataset items to our CSV shape."""
    nested = item.get("job") if isinstance(item.get("job"), dict) else {}
    company_block = item.get("company") if isinstance(item.get("company"), dict) else {}
    org = item.get("organization") if isinstance(item.get("organization"), dict) else {}

    title = _first_str(
        item,
        "title",
        "jobTitle",
        "job_title",
        "position",
        "positionName",
        "position_title",
        "name",
    ) or _first_str(nested, "title", "jobTitle", "name")

    company = _first_str(
        item,
        "companyName",
        "company_name",
        "employer",
        "employerName",
        "organizationName",
    ) or _first_str(company_block, "name", "companyName") or _first_str(org, "name", "title")
    if isinstance(item.get("company"), str):
        company = company or item["company"].strip()

    location = _first_str(
        item,
        "location",
        "jobLocation",
        "formattedLocation",
        "city",
        "region",
        "country",
    ) or _first_str(nested, "location", "city")
    if not location:
        location = fallback_location

    job_url = _first_str(
        item,
        "url",
        "jobUrl",
        "job_url",
        "link",
        "applyUrl",
        "apply_url",
        "jobLink",
        "job_link",
        "externalUrl",
    ) or _first_str(nested, "url", "link", "applyUrl")

    description = _first_str(item, "description", "jobDescription", "snippet", "summary") or _first_str(
        nested, "description", "summary"
    )

    website = _first_str(
        item,
        "companyWebsite",
        "company_website",
        "website",
        "employerWebsite",
    ) or _first_str(company_block, "website", "url") or _first_str(org, "url", "website")

    email = _first_str(item, "email", "contactEmail", "recruiterEmail")

    return {
        "job_title": title,
        "company": company,
        "location": location,
        "job_url": job_url,
        "search_query": search_query,
        "description": description[:800],
        "source": "apify_jobs",
        "website": website,
        "email": email,
    }


def _merge_key(row: dict[str, str]) -> str | None:
    url = (row.get("job_url") or "").strip().lower()
    if url and url not in ("http://", "https://"):
        return url
    title = (row.get("job_title") or "").strip().lower()
    company = (row.get("company") or "").strip().lower()
    location = (row.get("location") or "").strip().lower()
    if title or company:
        return f"{title}|{company}|{location}"
    desc = (row.get("description") or "").strip()
    if len(desc) >= 40:
        return f"desc:{hash(desc)}"
    return None


def _is_us_job(row: dict[str, str]) -> bool:
    blob = f"{row.get('location', '')} {row.get('search_query', '')} {row.get('description', '')[:200]}"
    if NON_US_LOCATION_HINT.search(blob):
        return False
    return bool(US_LOCATION_HINT.search(blob))


def _apify_download_dataset(token: str, dataset_id: str) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?offset={offset}&limit=1000&clean=1&token={token}"
        )
        with urllib.request.urlopen(url, timeout=120) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return items


def _apify_import_runs(token: str, since_date: str, actor_id: str = APIFY_JOBS_ACTOR) -> list[tuple[str, str, list[dict]]]:
    """Return (search_query, location, items) for each succeeded actor run on/after since_date."""
    out: list[tuple[str, str, list[dict]]] = []
    offset = 0
    while True:
        list_url = (
            f"https://api.apify.com/v2/acts/{actor_id}/runs"
            f"?token={token}&limit=100&offset={offset}&desc=1"
        )
        with urllib.request.urlopen(list_url, timeout=120) as resp:
            payload = json.loads(resp.read())["data"]
        runs = payload.get("items") or []
        if not runs:
            break
        stop = False
        for run in runs:
            started = (run.get("startedAt") or "")[:10]
            if started < since_date:
                stop = True
                break
            if run.get("status") != "SUCCEEDED":
                continue
            inp = run.get("input") or run.get("defaultRunOptions", {}).get("input") or {}
            if isinstance(inp, str):
                try:
                    inp = json.loads(inp)
                except json.JSONDecodeError:
                    inp = {}
            q = (inp.get("searchQuery") or inp.get("query") or "unknown").strip()
            loc = (inp.get("location") or "unknown").strip()
            ds = run.get("defaultDatasetId")
            if not ds:
                continue
            items = _apify_download_dataset(token, ds)
            out.append((q, loc, items))
        if stop or len(runs) < 100:
            break
        offset += 100
    return out


def _apify_run(
    token: str,
    search_query: str,
    location: str,
    max_results: int,
    hours_old: int = 336,
) -> list[dict]:
    payload = {
        "searchQuery": search_query,
        "location": location,
        "platforms": ["indeed", "linkedin"],
        "maxResults": max_results,
        "deduplicate": True,
        # Wider window = more inventory per query (168≈1 week was returning ~25 for many US searches)
        "hoursOld": hours_old,
    }
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{APIFY_JOBS_ACTOR}/runs?token={token}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        run = json.loads(resp.read())["data"]
    run_id = run["id"]
    for _ in range(120):
        with urllib.request.urlopen(f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}", timeout=120) as resp:
            data = json.loads(resp.read())["data"]
        if data["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            if data["status"] != "SUCCEEDED":
                raise RuntimeError(f"Apify run failed: {data['status']}")
            dataset_id = data["defaultDatasetId"]
            break
        time.sleep(10)
    else:
        raise RuntimeError("Apify run timeout")

    items: list[dict] = []
    offset = 0
    while True:
        sep = "&"
        url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?offset={offset}&limit=1000&clean=1&token={token}"
        )
        with urllib.request.urlopen(url, timeout=120) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return items


def _slug_company(name: str) -> str:
    n = SUFFIX_DROP.sub("", name.lower())
    return re.sub(r"[^a-z0-9]+", "", n)[:40]


def _resolve_websites_and_emails(
    rows: list[dict[str, str]],
    out_date: str,
    delay: float,
    probe_delay: float,
    *,
    country: str = "GB",
) -> list[dict[str, str]]:
    need_site = [r for r in rows if not (r.get("website") or "").strip() and (r.get("company") or r.get("business_name"))]
    if not need_site:
        return rows

    site_in = EXPORTS / f"jobs_website_resolve_in_{out_date}.csv"
    site_out = EXPORTS / f"jobs_website_resolved_{out_date}.csv"
    with site_in.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/find_company_websites.py"),
            str(site_in),
            "--out",
            str(site_out),
            "--skip-recruiters",
            "--country",
            country,
            "--delay",
            str(max(delay, 0.5)),
        ],
        check=True,
        cwd=ROOT,
    )

    resolved = list(csv.DictReader(site_out.open(encoding="utf-8")))
    by_job = {(r.get("job_url") or "").lower(): r for r in resolved}

    probe_in = EXPORTS / f"jobs_email_probe_in_{out_date}.csv"
    probe_out = EXPORTS / f"jobs_email_probed_{out_date}.csv"
    to_probe = [by_job.get((r.get("job_url") or "").lower(), r) for r in rows]
    to_probe = [r for r in to_probe if (r.get("website") or "").strip()]
    if not to_probe:
        return resolved

    with probe_in.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(to_probe)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/enrich_csv_emails_from_websites.py"),
            str(probe_in),
            "--out",
            str(probe_out),
            "--delay",
            str(probe_delay),
            "--timeout",
            "6",
        ],
        check=True,
        cwd=ROOT,
    )

    probed = {(r.get("job_url") or "").lower(): r for r in csv.DictReader(probe_out.open(encoding="utf-8"))}
    out: list[dict[str, str]] = []
    for r in resolved:
        row = dict(r)
        pr = probed.get((row.get("job_url") or "").lower())
        if pr:
            email = (pr.get("email") or pr.get("enrichment_best_email") or "").strip()
            if email:
                row["email"] = email
        out.append(row)
    return out


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--use-apify", action="store_true", help="Run new Apify Indeed/LinkedIn scrapes")
    ap.add_argument(
        "--import-apify-since",
        metavar="YYYY-MM-DD",
        help="Download & merge existing Apify actor runs since date (no new scrapes)",
    )
    ap.add_argument(
        "--apify-max-results",
        type=int,
        default=250,
        help="Max jobs per Apify query/location (actor max 1000; default 250)",
    )
    ap.add_argument(
        "--hours-old",
        type=int,
        default=336,
        help="Only jobs posted within this many hours (default 336 = 14 days; was 168)",
    )
    ap.add_argument("--probe-emails", action="store_true", help="Resolve company websites (DDG) and probe for emails")
    ap.add_argument("--us-only", action="store_true", help="US Apify queries only; skip Reed/Arbeitnow; US output filenames")
    ap.add_argument(
        "--us-broad-only",
        action="store_true",
        help="With --us-only: only nationwide US queries (skip city-level runs — fewer Apify runs, more per run)",
    )
    ap.add_argument("--website-delay", type=float, default=1.0, help="Delay between DuckDuckGo website lookups")
    ap.add_argument("--probe-delay", type=float, default=0.35)
    ap.add_argument("--country", choices=("GB", "US"), default=None, help="Website lookup region (default: US if --us-only else GB)")
    ap.add_argument("--matrix", action="store_true", help="Scale mode: every US_TITLES x US_METROS pair as its own search")
    ap.add_argument("--max-searches", type=int, default=0, help="Cap matrix searches (0 = all ~360)")
    ap.add_argument("--dry-run", action="store_true", help="Print the search plan and exit without calling Apify")
    ap.add_argument("--concurrency", type=int, default=1, help="Parallel Apify runs (1 = sequential; 6-8 is a good default)")
    args = ap.parse_args()

    country = args.country or ("US" if args.us_only else "GB")
    if args.matrix:
        apify_queries = build_matrix(US_TITLES, US_METROS, args.max_searches)
    elif args.us_only:
        if args.us_broad_only:
            # Nationwide only — ~9 runs instead of ~19 city+national
            apify_queries = [ql for ql in APIFY_QUERIES_US if ql[1] in ("United States", "Remote")]
        else:
            apify_queries = APIFY_QUERIES_US
    else:
        apify_queries = APIFY_QUERIES

    if args.dry_run:
        by_metro: dict[str, int] = {}
        for _t, m in apify_queries:
            by_metro[m] = by_metro.get(m, 0) + 1
        print(f"[dry-run] {len(apify_queries)} Apify searches planned across {len(by_metro)} locations")
        print(f"[dry-run] cap per search: {args.apify_max_results} -> ceiling {len(apify_queries) * args.apify_max_results} rows")
        for m, c in list(by_metro.items())[:20]:
            print(f"    {m:<24} {c} searches")
        print("[dry-run] no Apify credits spent; drop --dry-run to execute")
        return
    slug = "us" if args.us_only else "smm_intent"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; Lumo22JobScraper/1.0)"}
    merged: dict[str, dict[str, str]] = {}
    sources: list[dict[str, str | int]] = []

    token = os.getenv("APIFY_TOKEN", "").strip() or os.getenv("APIFY_API_TOKEN", "").strip()

    def _ingest_apify_items(items: list[dict], q: str, loc: str) -> None:
        sources.append({"source": "apify", "query": q, "location": loc, "count": len(items)})
        for item in items:
            row = _apify_item_to_row(item, q, loc)
            key = _merge_key(row)
            if key:
                merged[key] = row

    if args.import_apify_since and token:
        print(f"[apify] importing succeeded runs since {args.import_apify_since}")
        for q, loc, items in _apify_import_runs(token, args.import_apify_since):
            _ingest_apify_items(items, q, loc)
    elif args.use_apify and token:
        print(
            f"[apify] {len(apify_queries)} query run(s) | maxResults={args.apify_max_results} | "
            f"hoursOld={args.hours_old}",
            flush=True,
        )
        def _one_search(pair: tuple[str, str]):
            """Run a single Apify search. Returns (query, location, items, error)."""
            q, loc = pair
            try:
                items = _apify_run(
                    token, q, loc, args.apify_max_results, hours_old=args.hours_old
                )
                return (q, loc, items, None)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                return (q, loc, [], f"HTTP {e.code} {body[:200]}")
            except Exception as e:  # pragma: no cover - network transient
                return (q, loc, [], str(e))

        if args.concurrency > 1:
            # Each actor run costs minutes of startup and scrape latency, so sequential
            # execution — not credits or result caps — is what makes a wide matrix
            # impractical: 40 searches measured at ~10 min each is a 6-hour run. The work is
            # entirely I/O wait, so a thread pool collapses that to roughly wall-time / N.
            # Results are ingested on this thread as futures land, keeping `merged` single-writer.
            from concurrent.futures import ThreadPoolExecutor, as_completed

            done = 0
            total = len(apify_queries)
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [pool.submit(_one_search, pair) for pair in apify_queries]
                for fut in as_completed(futures):
                    q, loc, items, err = fut.result()
                    done += 1
                    if err:
                        print(f"[apify] ({done}/{total}) skipped {q!r} @ {loc}: {err}", flush=True)
                    else:
                        print(f"[apify] ({done}/{total}) {q!r} @ {loc} → {len(items)} jobs", flush=True)
                        _ingest_apify_items(items, q, loc)
        else:
            for i, (q, loc) in enumerate(apify_queries, 1):
                print(f"[apify] ({i}/{len(apify_queries)}) {q!r} @ {loc} …", flush=True)
                q, loc, items, err = _one_search((q, loc))
                if err:
                    print(f"[apify] skipped {q!r} @ {loc}: {err}")
                else:
                    print(f"[apify]   → {len(items)} jobs", flush=True)
                    _ingest_apify_items(items, q, loc)

    if not args.us_only:
        for url, loc, q in REED_SEARCHES:
            try:
                rows = _parse_reed(url, loc, q, headers)
                sources.append({"source": "reed", "query": q, "count": len(rows)})
                for row in rows:
                    key = row["job_url"].lower()
                    merged[key] = row
            except Exception as e:
                print(f"[reed] failed {q}: {e}")
            time.sleep(1)

        try:
            arbeit = _fetch_arbeitnow(8, headers)
            sources.append({"source": "arbeitnow", "query": "marketing_filter", "count": len(arbeit)})
            for row in arbeit:
                key = (row.get("job_url") or row.get("job_title", "")).lower()
                if key:
                    merged[key] = row
        except Exception as e:
            print(f"[arbeitnow] failed: {e}")

    all_rows = [_to_row(r) for r in merged.values()]
    filtered = []
    for r in all_rows:
        blob = f"{r.get('job_title', '')} {r.get('company', '')} {r.get('description', '')}"
        if not INCLUDE.search(blob):
            continue
        if EXCLUDE.search(blob) and not re.search(r"social media|instagram|content creator", blob, re.I):
            continue
        if args.us_only and not _is_us_job(r):
            continue
        filtered.append(r)

    if args.probe_emails:
        filtered = _resolve_websites_and_emails(
            filtered,
            args.date,
            args.website_delay,
            args.probe_delay,
            country=country,
        )

    raw_csv = EXPORTS / f"jobs_raw_{slug}_{args.date}.csv"
    ready_csv = EXPORTS / f"smartlead_ready_jobs_{slug}_{args.date}.csv"
    new_only_csv = EXPORTS / f"smartlead_new_only_jobs_{slug}_{args.date}.csv"
    EXPORTS.mkdir(parents=True, exist_ok=True)

    for path, rows in ((raw_csv, all_rows), (ready_csv, filtered)):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    importable = [r for r in filtered if (r.get("email") or "").strip()]
    with new_only_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(importable)

    summary = {
        "date": args.date,
        "sources": sources,
        "raw_unique": len(all_rows),
        "filtered_relevant": len(filtered),
        "with_email": len(importable),
        "raw_csv": str(raw_csv.relative_to(ROOT)),
        "ready_csv": str(ready_csv.relative_to(ROOT)),
        "new_only_csv": str(new_only_csv.relative_to(ROOT)),
    }
    summary_path = EXPORTS / f"jobs_scrape_summary_{args.date}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
