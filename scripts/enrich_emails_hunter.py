#!/usr/bin/env python3
"""
Enrich company domains with Hunter Domain Search (prefer non-generic emails).

Requires HUNTER_API_KEY in .env (Hunter → API → Your API key).
Docs: https://hunter.io/api-documentation/v2#domain-search

Usage:
  python3 scripts/enrich_emails_hunter.py exports/hunter_domains_us_jobs_2026-07-17.csv \\
    --out exports/smartlead_us_upload_2026-07-17_hunter.csv

  # Dry-run first 5 domains (uses credits only for those 5):
  python3 scripts/enrich_emails_hunter.py exports/hunter_domains_us_jobs_2026-07-17.csv \\
    --out /tmp/hunter_test.csv --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://api.hunter.io/v2/domain-search"

GENERIC_LOCALS = frozenset(
    {
        "info",
        "hello",
        "hi",
        "contact",
        "support",
        "sales",
        "admin",
        "office",
        "team",
        "careers",
        "jobs",
        "hr",
        "marketing",
        "press",
        "media",
        "help",
        "customerservice",
        "reservations",
        "shop",
        "vendors",
        "feedback",
        "enquiries",
        "inquiries",
        "frontdesk",
        "noreply",
        "no-reply",
    }
)

PREFERRED_DEPTS = ("executive", "management", "marketing", "communication", "operations")
PREFERRED_SENIORITY = ("executive", "senior", "owner")


def _domain_from_row(row: dict[str, str]) -> str:
    d = (row.get("domain") or "").strip().lower().removeprefix("www.")
    if d:
        return d
    website = (row.get("website") or "").strip()
    if website:
        host = urlparse(website if "://" in website else f"https://{website}").hostname or ""
        return host.lower().removeprefix("www.")
    email = (row.get("email") or row.get("current_email") or "").strip().lower()
    if "@" in email:
        return email.split("@", 1)[1]
    return ""


def _save_cache(path, cache: dict) -> None:
    """
    Persist paid lookups. Called after every new search rather than only at the end: a run that
    dies partway (quota exhausted, Ctrl-C, network) would otherwise throw away results already
    paid for, and the re-run would buy them again.
    """
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache))
    except Exception as e:
        print(f"[cache] could not save ({e})", flush=True)


def _company_from_row(row: dict[str, str]) -> str:
    """
    Company name, used when the row carries no domain at all.

    Job-board rows (Apify jobs actor) arrive with company/job_title/job_url and nothing else —
    no website, no email — so requiring a domain dropped every one of them before Hunter was
    ever called. Hunter's Domain Search takes `company` as an alternative to `domain` and
    resolves the name itself, which beats guessing a domain from the name string.
    """
    for key in ("company_name", "company", "business_name"):
        v = (row.get(key) or "").strip()
        if v:
            return v
    return ""


def _score_email(item: dict) -> tuple[int, str]:
    """Higher is better. Prefer personal/named over generic."""
    email = (item.get("value") or "").strip().lower()
    if not email or "@" not in email:
        return (-999, "")
    local = email.split("@", 1)[0]
    score = int(item.get("confidence") or 0)
    if local in GENERIC_LOCALS or local.startswith(("info", "hello", "contact", "support")):
        score -= 80
    else:
        score += 40
    dept = (item.get("department") or "").lower()
    if any(d in dept for d in PREFERRED_DEPTS):
        score += 25
    sen = (item.get("seniority") or "").lower()
    if any(s in sen for s in PREFERRED_SENIORITY):
        score += 20
    # Prefer verified-ish
    if item.get("verification", {}).get("status") == "valid":
        score += 15
    return (score, email)


def hunter_domain_search(
    api_key: str, domain: str = "", company: str = "", timeout: int = 30
) -> dict:
    """
    Domain Search by domain when we have one, otherwise by company name.

    Hunter requires at least one of the two and prefers domain ("we won't have to find it"),
    so domain wins when both are present.
    """
    if not domain and not company:
        raise ValueError("hunter_domain_search needs a domain or a company name")
    key = {"domain": domain} if domain else {"company": company}
    r = requests.get(
        BASE,
        params={
            **key,
            "api_key": api_key,
            "limit": 10,
            "type": "personal",  # prefer personal; fall back without if empty
        },
        timeout=timeout,
    )
    if r.status_code == 400:
        # Some domains reject type=personal — retry without
        r = requests.get(
            BASE,
            params={**key, "api_key": api_key, "limit": 10},
            timeout=timeout,
        )
    r.raise_for_status()
    return r.json()


def pick_best(data: dict) -> tuple[str, str, str, str, int]:
    """Return email, first_name, last_name, position, confidence."""
    emails = (data.get("data") or {}).get("emails") or []
    if not emails:
        return "", "", "", "", 0
    ranked = sorted(emails, key=_score_email, reverse=True)
    best = ranked[0]
    email = (best.get("value") or "").strip().lower()
    return (
        email,
        (best.get("first_name") or "").strip(),
        (best.get("last_name") or "").strip(),
        (best.get("position") or "").strip(),
        int(best.get("confidence") or 0),
    )


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.35, help="Seconds between Hunter calls")
    ap.add_argument("--min-confidence", type=int, default=50)
    ap.add_argument(
        "--cache",
        type=Path,
        default=ROOT / "exports" / "hunter_lookup_cache.json",
        help="Reuse previous lookups instead of re-spending credits. Pass '' to disable.",
    )
    args = ap.parse_args()

    api_key = os.getenv("HUNTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "HUNTER_API_KEY missing in .env\n"
            "Get it from https://hunter.io/api-keys → paste:\n"
            "  HUNTER_API_KEY=your_key_here"
        )

    with args.input_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if args.limit > 0:
        rows = rows[: args.limit]

    # Hunter charges per search, and job-board exports repeat the same employer across several
    # postings (372 rows / 328 companies in the July US batch). Cache on disk so duplicates and
    # re-runs are free — without it a second run costs full price for the same answers.
    cache: dict[str, dict] = {}
    if args.cache and args.cache.exists():
        try:
            cache = json.loads(args.cache.read_text())
            print(f"[cache] loaded {len(cache)} previous lookups from {args.cache}")
        except Exception as e:
            print(f"[cache] ignoring unreadable cache ({e})")

    out_rows: list[dict[str, str]] = []
    found = 0
    spent = 0
    cached_hits = 0
    for i, row in enumerate(rows, 1):
        domain = _domain_from_row(row)
        company = _company_from_row(row)
        current = (row.get("current_email") or row.get("email") or "").strip().lower()
        result = {
            "email": current,
            "company_name": company,
            "first_name": "",
            "last_name": "",
            "job_title": (row.get("job_title") or "").strip(),
            "personalization_line": (row.get("personalization_line") or "").strip(),
            "job_url": (row.get("job_url") or "").strip(),
            "website": (row.get("website") or "").strip(),
            "city": (row.get("city") or "").strip(),
            "hunter_domain": domain,
            "hunter_email": "",
            "hunter_position": "",
            "hunter_confidence": "",
            "hunter_status": "",
        }
        if not domain and not company:
            result["hunter_status"] = "skipped_no_domain_or_company"
            out_rows.append(result)
            print(f"[{i}/{len(rows)}] [skip] row has neither domain nor company name", flush=True)
            continue
        lookup_key = f"d:{domain}" if domain else f"c:{company.lower()}"
        result["hunter_lookup"] = "domain" if domain else "company"
        was_cached = lookup_key in cache
        try:
            if lookup_key in cache:
                payload = cache[lookup_key]
                cached_hits += 1
            else:
                payload = hunter_domain_search(api_key, domain=domain, company=company)
                cache[lookup_key] = payload
                spent += 1
                _save_cache(args.cache, cache)
            # Hunter returns the domain it resolved the company to — keep it for the next run.
            resolved = ((payload.get("data") or {}).get("domain") or "").strip().lower()
            if resolved and not domain:
                result["hunter_domain"] = resolved
            email, first, last, position, conf = pick_best(payload)
            if email and conf >= args.min_confidence:
                result["hunter_email"] = email
                result["hunter_position"] = position
                result["hunter_confidence"] = str(conf)
                result["first_name"] = first
                result["last_name"] = last
                # Prefer Hunter named email over current generic
                cur_local = current.split("@")[0] if "@" in current else ""
                if cur_local in GENERIC_LOCALS or not current:
                    result["email"] = email
                    result["hunter_status"] = "replaced_with_hunter"
                elif email != current:
                    result["email"] = email
                    result["hunter_status"] = "upgraded_to_hunter"
                else:
                    result["hunter_status"] = "confirmed_same"
                found += 1
                print(f"[{i}/{len(rows)}] [ok] {company} -> {email} ({conf})", flush=True)
            else:
                result["hunter_status"] = "no_personal_email"
                print(f"[{i}/{len(rows)}] [miss] {company} ({domain})", flush=True)
        except requests.HTTPError as e:
            body = e.response.text[:200] if e.response is not None else ""
            result["hunter_status"] = f"http_{e.response.status_code if e.response else '?'}"
            print(f"[{i}/{len(rows)}] [err] {company}: {e} {body}", flush=True)
            if e.response is not None and e.response.status_code in (401, 403):
                raise SystemExit("Hunter API key rejected — check HUNTER_API_KEY") from e
            if e.response is not None and e.response.status_code == 429:
                # Two very different 429s share this code. "Too fast" clears after a pause;
                # "plan allowance used up" does not clear until the billing period rolls over,
                # and retrying it just hangs the run for minutes per row.
                quota_exhausted = "billing period" in body.lower() or "included in your plan" in body.lower()
                if quota_exhausted:
                    _save_cache(args.cache, cache)
                    raise SystemExit(
                        "\nHunter search allowance for this billing period is used up — "
                        "every remaining row would fail the same way.\n"
                        f"  rows processed before stopping: {i - 1}\n"
                        f"  paid lookups saved to cache:    {spent}\n"
                        "Check plan/renewal at https://hunter.io/api-keys, then re-run: "
                        "cached rows cost nothing the second time."
                    ) from e
                print("Rate limited (too fast) — sleeping 30s", flush=True)
                time.sleep(30)
        except Exception as e:
            result["hunter_status"] = "error"
            print(f"[{i}/{len(rows)}] [err] {company}: {e}", flush=True)
        out_rows.append(result)
        # Only a real API call needs pacing; cache hits are local and free.
        if not was_cached:
            time.sleep(args.delay)

    fields = list(out_rows[0].keys()) if out_rows else [
        "email",
        "company_name",
        "first_name",
        "last_name",
        "job_title",
        "personalization_line",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    # Slim Smartlead-ready copy
    slim = args.out.with_name(args.out.stem + "_smartlead.csv")
    slim_fields = [
        "email",
        "company_name",
        "first_name",
        "last_name",
        "job_title",
        "personalization_line",
        "job_url",
        "website",
        "city",
    ]
    with slim.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=slim_fields)
        w.writeheader()
        for r in out_rows:
            if (r.get("email") or "").strip():
                w.writerow({k: r.get(k, "") for k in slim_fields})

    _save_cache(args.cache, cache)

    sendable = sum(1 for r in out_rows if (r.get("email") or "").strip())
    by_lookup = {"domain": 0, "company": 0}
    for r in out_rows:
        if (r.get("email") or "").strip() and r.get("hunter_lookup") in by_lookup:
            by_lookup[r["hunter_lookup"]] += 1

    print(f"\nWrote {args.out} ({len(out_rows)} rows, hunter hits={found})")
    print(f"Smartlead import: {slim}")
    print("\n--- funnel ---")
    print(f"  rows in ................. {len(out_rows)}")
    print(f"  sendable (has email) .... {sendable}  ({100.0 * sendable / len(out_rows) if out_rows else 0:.0f}%)")
    print(f"    via known domain ...... {by_lookup['domain']}")
    print(f"    via company name ...... {by_lookup['company']}")
    print(f"  API searches spent ...... {spent}")
    print(f"  served from cache ....... {cached_hits}  (free)")


if __name__ == "__main__":
    main()
