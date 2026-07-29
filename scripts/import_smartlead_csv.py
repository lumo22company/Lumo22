#!/usr/bin/env python3
"""
Import leads from CSV into a Smartlead campaign via API.

  python3 scripts/import_smartlead_csv.py exports/smartlead_us_import_2026-07-02.csv \\
    --campaign-id 3521696

Requires SMARTLEAD_API_KEY in .env.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"


def _norm(s: str) -> str:
    return (s or "").strip()


def _payload_row(row: dict[str, str]) -> dict | None:
    email = _norm(row.get("email", ""))
    if not email:
        return None
    company = _norm(row.get("business_name") or row.get("company") or row.get("company_name"))
    custom: dict[str, str] = {
        "company_name": company,
        "job_title": _norm(row.get("job_title")),
        "personalization_line": _norm(row.get("personalization_line")),
        "job_url": _norm(row.get("job_url")),
        "website": _norm(row.get("website")),
        "city": _norm(row.get("city")),
    }
    custom = {k: v for k, v in custom.items() if v}
    return {
        "email": email,
        "first_name": _norm(row.get("first_name") or row.get("firstName")),
        "last_name": _norm(row.get("last_name") or row.get("lastName")),
        "custom_fields": custom,
    }


def _import_chunks(
    campaign_id: str,
    api_key: str,
    leads: list[dict],
    batch_size: int,
    dry_run: bool,
) -> tuple[int, int]:
    imported = 0
    failed = 0
    endpoint = (
        f"{BASE}/campaigns/{campaign_id}/leads"
        f"?api_key={urllib.parse.quote(api_key)}"
    )
    for i in range(0, len(leads), batch_size):
        chunk = leads[i : i + batch_size]
        if dry_run:
            print(f"  [dry-run] would import {len(chunk)} leads", flush=True)
            imported += len(chunk)
            continue
        payload = json.dumps({"lead_list": chunk}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            print(f"  imported {len(chunk)} leads (batch {i // batch_size + 1})", flush=True)
            if body.strip():
                print(f"    response: {body[:200]}", flush=True)
            imported += len(chunk)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            print(f"  HTTP {e.code} batch {i // batch_size + 1}: {err[:400]}", flush=True)
            failed += len(chunk)
        except Exception as e:
            print(f"  failed batch {i // batch_size + 1}: {e}", flush=True)
            failed += len(chunk)
    return imported, failed


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("--campaign-id", default="3521696")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        raise SystemExit("SMARTLEAD_API_KEY missing — add to .env (Smartlead → Settings → API)")

    with args.csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    leads = [p for r in rows if (p := _payload_row(r))]

    print(f"Campaign {args.campaign_id} | {len(leads)} leads from {args.csv_path}", flush=True)
    if not leads:
        raise SystemExit("No leads with email in CSV")

    imported, failed = _import_chunks(
        args.campaign_id, api_key, leads, args.batch_size, args.dry_run
    )
    print(f"\nDone: imported={imported} failed={failed}", flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
