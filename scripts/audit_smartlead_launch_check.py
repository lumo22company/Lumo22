#!/usr/bin/env python3
"""Launch readiness check for US jobs + aesthetics Smartlead campaigns."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGNS = {
    "3521696": "US Hiring SMM (jobs)",
    "3607862": "US Aesthetics TX/LA",
}


def get(api_key: str, path: str, params: dict | None = None):
    q = {"api_key": api_key, **(params or {})}
    r = requests.get(f"{BASE}{path}", params=q, timeout=45)
    try:
        data = r.json()
    except Exception:
        data = r.text
    return r.status_code, data


def main() -> None:
    load_dotenv(ROOT / ".env", override=True)
    api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()
    ok: list[str] = []
    issues: list[str] = []

    print("=== Smartlead launch check ===\n")
    if not api_key:
        print("FAIL: SMARTLEAD_API_KEY missing in .env")
        raise SystemExit(1)
    ok.append(f"API key loaded ({len(api_key)} chars)")

    code, _ = get(api_key, "/campaigns/")
    if code != 200:
        print(f"FAIL: cannot list campaigns (HTTP {code})")
        raise SystemExit(1)
    ok.append("API connection OK")

    for cid, label in CAMPAIGNS.items():
        print(f"\n--- {label} ({cid}) ---")
        code, c = get(api_key, f"/campaigns/{cid}")
        if code != 200:
            issues.append(f"{label}: cannot fetch campaign (HTTP {code})")
            continue
        if isinstance(c, dict) and "data" in c:
            c = c["data"]

        name = c.get("name") or "?"
        status = str(c.get("status") or "?").upper()
        print(f"Name: {name}")
        print(f"Status: {status}")
        ok.append(f"{label}: found ({status})")
        if status in ("DRAFT", "PAUSED", "DRAFTED"):
            issues.append(f"{label}: status is {status} — not sending")
        elif status in ("ACTIVE", "START", "STARTED"):
            ok.append(f"{label}: ACTIVE")

        # Settings often nested or top-level depending on API version
        plain = c.get("send_as_plain_text")
        unsub = c.get("unsubscribe_text") or ""
        max_day = c.get("max_leads_per_day")
        follow = c.get("follow_up_percentage")
        tz = c.get("timezone") or c.get("scheduler_cron_value")
        print(f"plain_text={plain} max_leads_per_day={max_day} follow_up_percentage={follow}")
        print(f"timezone/schedule={tz}")
        print(f"unsubscribe_text set: {bool(str(unsub).strip())}")
        if plain is True:
            issues.append(f"{label}: send_as_plain_text ON — can strip HTML/unsubscribe links")
        if max_day and int(max_day) > 30:
            issues.append(f"{label}: max_leads_per_day={max_day} is high for one inbox")

        code, seqs = get(api_key, f"/campaigns/{cid}/sequences")
        if isinstance(seqs, dict):
            seqs = seqs.get("sequences") or seqs.get("data") or []
        if not isinstance(seqs, list) or not seqs:
            issues.append(f"{label}: no sequences")
            continue
        ok.append(f"{label}: {len(seqs)} sequence step(s)")
        for i, s in enumerate(seqs, 1):
            subj = s.get("subject") or ""
            body = s.get("email_body") or s.get("body") or ""
            print(f"  Email {i}: {subj[:80]}")
            has_sample = "captions-sample" in body
            has_pers = "{{personalization_line}}" in body or "{{personalization_line}}" in subj
            has_co = "{{company_name}}" in body or "{{company_name}}" in subj
            print(f"    sample CTA={has_sample} personalization={has_pers} company={has_co}")
            if i == 1:
                if not has_sample:
                    issues.append(f"{label}: Email 1 missing /captions-sample link")
                else:
                    ok.append(f"{label}: Email 1 has sample CTA")
                if not has_pers:
                    issues.append(f"{label}: Email 1 missing {{{{personalization_line}}}}")
                if not has_co:
                    issues.append(f"{label}: Email 1 missing {{{{company_name}}}}")

        code, acc = get(api_key, f"/campaigns/{cid}/email-accounts")
        if isinstance(acc, dict):
            acc = acc.get("data") or acc.get("email_accounts") or []
        senders = []
        if isinstance(acc, list):
            for a in acc:
                senders.append((a.get("from_email") or a.get("email") or "").lower())
        print(f"Senders: {senders or 'NONE'}")
        if not senders:
            issues.append(f"{label}: no sender attached")
        elif "sophie@lumo22.com" in senders:
            ok.append(f"{label}: sophie@ attached")
        else:
            issues.append(f"{label}: unexpected senders {senders}")

        code, leads = get(api_key, f"/campaigns/{cid}/leads", {"limit": 1, "offset": 0})
        total = 0
        if isinstance(leads, dict):
            total = int(leads.get("total_leads") or leads.get("total") or 0)
        print(f"Leads: {total}")
        if total == 0:
            issues.append(f"{label}: no leads")
        else:
            ok.append(f"{label}: {total} leads")

    print("\n=== PASS ===")
    for x in ok:
        print(f"  ✓ {x}")
    print("\n=== CHECK / FIX ===")
    if not issues:
        print("  (none)")
    for x in issues:
        print(f"  • {x}")
    print("\nMANUAL (API cannot fully verify):")
    print("  • Unsubscribe: Settings → Add unsubscribe message in all emails ON")
    print("  • Test emails: unsubscribe link intentionally unclickable")
    print("  • Optimize Email Delivery / plain text OFF if you need clickable HTML links")
    print(f"\n{'LOOKS GOOD — monitor opens/clicks' if not issues else 'FIX ITEMS ABOVE'}")


if __name__ == "__main__":
    main()
