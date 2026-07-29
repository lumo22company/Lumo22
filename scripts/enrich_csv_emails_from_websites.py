#!/usr/bin/env python3
"""
Extract published emails from website HTML for outreach CSV rows (homepage + light /contact probes).

Uses only stdlib parsing + requests (no Hunter/Apollo keys). Intended for QC samples or small lists;
for large/high-throughput workloads use Apify contact actors instead.

Example:
  python scripts/enrich_csv_emails_from_websites.py exports/smartlead_super_safe_batch_100_balanced.csv \\
    --out exports/smartlead_enriched_email_probe.csv --limit 25 --delay 1.2
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from urllib.parse import urljoin, urlparse

import requests


def _norm_header(name: str) -> str:
    """Strip BOM and stray quotes from CSV header names (common with Excel/Apify exports)."""
    k = (name or "").lstrip("\ufeff").strip()
    if k.startswith('"') and k.endswith('"') and len(k) >= 2:
        k = k[1:-1]
    return k.strip()


def _normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    return {_norm_header(k): (v or "").strip() for k, v in row.items()}


EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

BLACKLIST_FULL = frozenset(
    {
        "user@domain.com",
        "name@company.com",
        "email@company.com",
        "yourname@yourcompany.com",
        "your@email.com",
        "name@email.com",
    }
)


BLACKLIST_SUBSTR = (
    "w3.org",
    "sentry.io",
    "example.com",
    "schema.org",
    "test@",
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
    "@2x.png",
    "@3x.png",
    "wordpress.com",
    "gravatar.com",
)

CONTACT_PATHS = ("/contact", "/contact-us", "/contactus", "/get-in-touch")


def normalize_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("//"):
        return "https:" + raw
    if not raw.startswith(("http://", "https://")):
        return "https://" + raw
    return raw


def site_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def extract_emails(html: str) -> set[str]:
    found: set[str] = set()
    for m in EMAIL_RE.finditer(html or ""):
        addr = m.group(0).lower().strip()
        if addr in BLACKLIST_FULL:
            continue
        if "@domain." in addr or "@company." in addr or "@example." in addr:
            continue
        if any(b in addr for b in BLACKLIST_SUBSTR):
            continue
        if addr.endswith((".png", ".jpg", ".gif", ".webp", ".svg")):
            continue
        found.add(addr)
    return found


def fetch_text(session: requests.Session, url: str, timeout: int) -> tuple[str | None, int | None]:
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400:
            return None, r.status_code
        if len(r.content) > 2_000_000:
            return None, r.status_code
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, r.status_code
    except Exception:
        return None, None


SHARED_INBOX_LOCALS = frozenset(
    {
        "info", "hello", "hi", "hey", "ask",
        "contact", "contactus",
        "enquiries", "enquiry", "inquiries", "inquiry",
        "bookings", "booking", "reservations",
        "office", "reception", "frontdesk",
        "sales", "team", "admin", "support",
        "membership", "members",
    }
)


def score_email(email: str, host_domain: str) -> int:
    """
    Rank candidate emails for cold-outreach reliability.

    For B2B outbound, shared/role inboxes (info@, hello@, enquiries@, etc.) are usually
    safer than first-name-only personal locals: they're less likely to bounce when staff
    leave, more likely to be monitored, and less likely to be a partial guess. Personal
    first-name-only locals (e.g. 'susie@', 'tom@') carry a small penalty; compound
    addresses (firstname.lastname) sit between the two.
    """
    edom = email.rsplit("@", 1)[-1]
    local = email.split("@", 1)[0]
    score = 0

    if host_domain and (edom == host_domain or edom.endswith("." + host_domain)):
        score += 100

    if local in SHARED_INBOX_LOCALS:
        score += 20
    elif any(sep in local for sep in (".", "_", "-")) or any(ch.isdigit() for ch in local):
        score += 5
    elif local.isalpha() and len(local) <= 8:
        score -= 10

    return score


def pick_best(emails: set[str], host_domain: str) -> tuple[str | None, int]:
    if not emails:
        return None, 0
    ranked = sorted(
        emails,
        key=lambda e: score_email(e, host_domain),
        reverse=True,
    )
    best = ranked[0]
    return best, score_email(best, host_domain)


def urls_to_try(base: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for u in [base.rstrip("/")] + [urljoin(base.rstrip("/") + "/", p.lstrip("/")) for p in CONTACT_PATHS]:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def run(
    input_path: str,
    output_path: str,
    limit: int | None,
    delay: float,
    timeout: int,
    website_col: str,
) -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    with open(input_path, newline="", encoding="utf-8-sig") as f_in:
        reader = csv.DictReader(f_in)
        if reader.fieldnames is None:
            raise SystemExit("Input CSV has no header row.")
        clean_fields = [_norm_header(h) for h in reader.fieldnames]
        if website_col not in clean_fields:
            raise SystemExit(
                f"Column {website_col!r} not in CSV headers after cleanup: {clean_fields}"
            )

        extras = ["enrichment_best_email", "enrichment_emails_seen", "enrichment_status"]
        all_rows = list(reader)
        total = len(all_rows) if limit is None else min(len(all_rows), limit)
        print(
            f"Email probe: {total} row(s) from {input_path} (delay={delay}s, timeout={timeout}s)",
            flush=True,
        )

        rows_out: list[dict[str, str]] = []
        n = 0
        for row in all_rows:
            if limit is not None and n >= limit:
                break
            n += 1

            row = _normalize_row_keys(row)
            company = (
                row.get("business_name")
                or row.get("company")
                or row.get("name")
                or f"row {n}"
            )
            url_raw = normalize_url(row.get(website_col, "") or "")
            merged_emails: set[str] = set()
            status_bits: list[str] = []

            if not url_raw:
                row = {**row, **dict.fromkeys(extras, "")}
                row["enrichment_status"] = "skipped_no_website"
                rows_out.append(row)
                print(f"[{n}/{total}] [skip] {company} (no website)", flush=True)
                continue

            host = site_domain(url_raw)
            if "instagram.com" in host or "facebook.com" in host or "linkedin.com" in host:
                row = {**row, **dict.fromkeys(extras, "")}
                row["enrichment_status"] = "skipped_social_only_url"
                rows_out.append(row)
                print(f"[{n}/{total}] [skip] {company} (social URL)", flush=True)
                time.sleep(delay)
                continue

            for u in urls_to_try(url_raw):
                html, code = fetch_text(session, u, timeout=timeout)
                if html:
                    merged_emails |= extract_emails(html)
                    status_bits.append(f"ok:{urlparse(u).path or '/'}")
                else:
                    bit = f"fail:{urlparse(u).path or '/'}"
                    if code:
                        bit += f":{code}"
                    status_bits.append(bit)

            best, _ = pick_best(merged_emails, host)
            row = {
                **row,
                "enrichment_best_email": best or "",
                "enrichment_emails_seen": ";".join(sorted(merged_emails)),
                "enrichment_status": (
                    f"emails={len(merged_emails)};" + ",".join(status_bits[:5])
                ),
            }
            rows_out.append(row)
            if best:
                print(f"[{n}/{total}] [ok] {company} -> {best}", flush=True)
            else:
                print(f"[{n}/{total}] [miss] {company} ({url_raw})", flush=True)
            time.sleep(delay)

    fieldnames = clean_fields + extras
    with open(output_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {output_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_csv", help="Input CSV with a website column")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max rows to process (default: all)",
    )
    ap.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between rows (default: 1.0)",
    )
    ap.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds")
    ap.add_argument(
        "--website-col",
        default="website",
        help="Column name for site URL (default: website)",
    )
    args = ap.parse_args()
    run(
        args.input_csv,
        args.out,
        args.limit,
        args.delay,
        args.timeout,
        args.website_col,
    )


if __name__ == "__main__":
    main()
