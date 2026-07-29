#!/usr/bin/env python3
"""Diagnose why Smartlead campaign 3521696 isn't sending."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = "3521696"


def _get(api_key: str, path: str) -> dict | list:
    q = urllib.parse.urlencode({"api_key": api_key})
    url = f"{BASE}{path}?{q}"
    with urllib.request.urlopen(url, timeout=45) as resp:
        return json.loads(resp.read())


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("SMARTLEAD_API_KEY missing in .env")

    now_et = datetime.now(ZoneInfo("America/New_York"))
    print(f"=== Diagnose campaign {CAMPAIGN_ID} ===")
    print(f"Now (US Eastern): {now_et.strftime('%A %Y-%m-%d %H:%M %Z')}\n")

    c = _get(api_key, f"/campaigns/{CAMPAIGN_ID}")
    if isinstance(c, dict) and "data" in c:
        c = c["data"]
    print(f"Name:   {c.get('name')}")
    print(f"Status: {c.get('status')}")

  # Leads
    try:
        leads = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/leads?limit=5&offset=0")
        if isinstance(leads, dict):
            total = leads.get("total_leads") or leads.get("total") or 0
            data = leads.get("data") or leads.get("leads") or []
        else:
            total = len(leads)
            data = leads
        print(f"\nLeads in campaign: {total}")
        if int(total or 0) == 0:
            print("  >>> BLOCKER: No leads imported. Upload smartlead_us_upload_2026-07-02.csv")
        else:
            for row in (data if isinstance(data, list) else [])[:3]:
                if isinstance(row, dict):
                    lead = row.get("lead") or row
                    print(
                        f"  sample: {lead.get('email')} | status={lead.get('status') or row.get('status')}"
                    )
    except Exception as e:
        print(f"\nLeads check failed: {e}")

    # Senders
    try:
        acc = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/email-accounts")
        if isinstance(acc, dict):
            acc = acc.get("data") or acc.get("email_accounts") or []
        if not acc:
            print("\n>>> BLOCKER: No sender mailbox attached to campaign")
        else:
            print("\nSenders attached:")
            for a in acc:
                print(
                    f"  {a.get('from_email') or a.get('email')} | "
                    f"warmup={a.get('warmup_enabled')} | "
                    f"status={a.get('smtp_success') or a.get('is_smtp_success') or '?'}"
                )
    except Exception as e:
        print(f"\nSender check failed: {e}")

    # Sequences
    try:
        seqs = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/sequences")
        if isinstance(seqs, dict):
            seqs = seqs.get("sequences") or seqs.get("data") or []
        print(f"\nSequence steps: {len(seqs) if isinstance(seqs, list) else seqs}")
        if not seqs:
            print("  >>> BLOCKER: No email sequence configured")
    except Exception as e:
        print(f"\nSequence check failed: {e}")

    # Schedule window hint
    hour = now_et.hour + now_et.minute / 60
    weekday = now_et.weekday()  # 0=Mon
    in_hours = weekday < 5 and 9.5 <= hour < 17
    print(f"\nIn send window (Mon-Fri 9:30-17:00 ET)? {'YES' if in_hours else 'NO — waits until next window'}")
    if not in_hours:
        print("  Campaign is active but Smartlead only sends during scheduled hours.")

    print("\n--- Common fixes ---")
    print("1. Leads tab → confirm 63 leads, status NOT all Completed/Paused")
    print("2. Email Accounts → sophie@lumo22.com connected (green), daily limit not 0")
    print("3. Schedule → max new leads/day = 5, timezone America/New_York")
    print("4. Mailboxes → sophie@ not disconnected or in warmup-only mode")


if __name__ == "__main__":
    main()
