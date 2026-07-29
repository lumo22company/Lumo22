#!/usr/bin/env python3
"""
Apify email enrichment — one website at a time, prints after each (no silent stalls).

  python3 scripts/enrich_emails_apify.py exports/jobs_us_smb_2026-07-02.csv \\
    --out exports/jobs_us_with_emails_apify_2026-07-02.csv --limit 25
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
APIFY_ACTOR = "vdrmota~contact-info-scraper"
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def _norm_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def _host(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _pick_email(candidates: list[str], host: str) -> str:
    seen: set[str] = set()
    cleaned: list[str] = []
    for c in candidates:
        e = c.lower().strip()
        if not e or e in seen:
            continue
        if any(x in e for x in ("example.com", "sentry", "wixpress", "schema.org")):
            continue
        seen.add(e)
        cleaned.append(e)
    if not cleaned:
        return ""

    def score(e: str) -> tuple[int, str]:
        local, _, dom = e.partition("@")
        s = 0
        if host and (dom == host or dom.endswith("." + host)):
            s += 10
        if local in ("info", "hello", "contact", "team", "sales", "support"):
            s += 5
        return (s, e)

    return sorted(cleaned, key=score, reverse=True)[0]


def _emails_from_item(item: dict) -> list[str]:
    out: list[str] = []
    for key in ("emails", "email", "mail", "contactEmail"):
        val = item.get(key)
        if isinstance(val, list):
            out.extend(str(x) for x in val if x)
        elif isinstance(val, str) and val.strip():
            out.append(val.strip())
    # scrape any email-like strings from nested dict
    blob = json.dumps(item)
    out.extend(EMAIL_RE.findall(blob))
    return out


def _apify_sync_one(token: str, url: str, timeout_sec: int = 120) -> list[str]:
    q = urllib.parse.urlencode({"token": token, "timeout": str(timeout_sec)})
    api_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items?{q}"
    body = json.dumps(
        {
            "startUrls": [{"url": url}],
            "maxDepth": 1,
            "sameDomain": True,
            "maxRequestsPerCrawl": 10,
        }
    ).encode()
    req = urllib.request.Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec + 30) as resp:
        items = json.loads(resp.read())
    if not isinstance(items, list):
        return []
    emails: list[str] = []
    for item in items:
        emails.extend(_emails_from_item(item))
    return emails


def main() -> None:
    print("enrich_emails_apify: starting", flush=True)
    load_dotenv(ROOT / ".env")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--website-col", default="website")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    token = os.getenv("APIFY_TOKEN", "").strip() or os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("APIFY_TOKEN missing — add it to .env in the project root.")
    print(f"Apify token loaded ({len(token)} chars)", flush=True)

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty csv: {args.input_csv}")

    fields = list(rows[0].keys())
    for col in ("enrichment_best_email", "enrichment_status"):
        if col not in fields:
            fields.append(col)

    todo: list[tuple[int, str, str, str]] = []
    for i, row in enumerate(rows):
        if (row.get("email") or row.get("enrichment_best_email") or "").strip():
            continue
        url = _norm_url(row.get(args.website_col, ""))
        if not url:
            continue
        company = row.get("business_name") or row.get("company") or _host(url)
        todo.append((i, url, _host(url), company))

    if args.limit is not None:
        todo = todo[: args.limit]

    print(f"Apify: {len(todo)} websites to probe (actor={APIFY_ACTOR})", flush=True)

    filled = 0
    for n, (idx, url, host, company) in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {company} — {url}", flush=True)
        try:
            emails = _apify_sync_one(token, url)
            best = _pick_email(emails, host)
        except urllib.error.HTTPError as e:
            print(f"  [apify fail] HTTP {e.code}", flush=True)
            time.sleep(args.delay)
            continue
        except Exception as e:
            print(f"  [apify fail] {e}", flush=True)
            time.sleep(args.delay)
            continue

        if best:
            row = rows[idx]
            row["enrichment_best_email"] = best
            if not (row.get("email") or "").strip():
                row["email"] = best
            row["enrichment_status"] = (row.get("enrichment_status") or "") + f";apify={best}"
            print(f"  [apify ok] -> {best}", flush=True)
            filled += 1
        else:
            print("  [apify miss] no email on site", flush=True)
        time.sleep(args.delay)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    total = sum(1 for r in rows if (r.get("email") or r.get("enrichment_best_email") or "").strip())
    print(f"Wrote {args.out} | apify filled {filled} | total with email {total}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
