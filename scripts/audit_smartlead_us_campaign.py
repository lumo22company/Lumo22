#!/usr/bin/env python3
"""Audit US SMM Smartlead campaign readiness for launch."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_ID = "3521696"
EXPECTED = {
    "name_contains": "US Hiring SMM",
    "sender_email": "sophie@lumo22.com",
    "sender_account_id": 18240835,
    "sequences": 3,
    "seq1_subject": "{{company_name}} — before the {{job_title}} hire?",
    "timezone": "America/New_York",
    "max_leads_per_day": 5,
    "merge_fields": ("company_name", "job_title", "personalization_line"),
    "cta_url": "https://www.lumo22.com/captions-sample",
    "upload_csv": "exports/smartlead_us_upload_2026-07-02.csv",
}


def _get(api_key: str, path: str) -> dict | list:
    q = urllib.parse.urlencode({"api_key": api_key})
    url = f"{BASE}{path}?{q}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()
    issues: list[str] = []
    ok: list[str] = []

    print(f"=== US SMM campaign audit ({CAMPAIGN_ID}) ===\n")

    # Local CSV check
    csv_path = ROOT / EXPECTED["upload_csv"]
    if csv_path.exists():
        import csv

        rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
        emails = sum(1 for r in rows if (r.get("email") or "").strip())
        ok.append(f"Import CSV ready: {csv_path.name} ({emails} leads)")
        for col in ("email", "company_name", "job_title", "personalization_line"):
            if col not in (rows[0].keys() if rows else []):
                issues.append(f"CSV missing column: {col}")
    else:
        issues.append(f"Import CSV missing: {csv_path}")

    if not api_key:
        issues.append("SMARTLEAD_API_KEY not in .env — cannot verify live campaign")
        _print_report(ok, issues)
        return

    try:
        campaign = _get(api_key, f"/campaigns/{CAMPAIGN_ID}")
    except Exception as e:
        issues.append(f"Cannot fetch campaign {CAMPAIGN_ID}: {e}")
        _print_report(ok, issues)
        return

    if isinstance(campaign, dict) and "data" in campaign:
        campaign = campaign["data"]

    name = campaign.get("name") or campaign.get("campaign_name") or ""
    status = campaign.get("status") or "unknown"
    ok.append(f"Campaign found: {name!r} (status: {status})")
    if EXPECTED["name_contains"].lower() not in name.lower():
        issues.append(f"Campaign name unexpected: {name!r}")

    # Sequences
    try:
        seqs = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/sequences")
        if isinstance(seqs, dict):
            seqs = seqs.get("sequences") or seqs.get("data") or []
        if len(seqs) >= EXPECTED["sequences"]:
            ok.append(f"Sequences: {len(seqs)} emails configured")
            s1 = seqs[0] if seqs else {}
            subj = s1.get("subject") or ""
            body = s1.get("email_body") or s1.get("body") or ""
            if EXPECTED["seq1_subject"] in subj:
                ok.append("Email 1 subject matches expected template")
            else:
                issues.append(f"Email 1 subject mismatch: {subj!r}")
            if EXPECTED["cta_url"] in body:
                ok.append("CTA link present in sequence")
            else:
                issues.append(f"CTA {EXPECTED['cta_url']} not found in email 1 body")
            for field in EXPECTED["merge_fields"]:
                if f"{{{{{field}}}}}" not in body and field not in subj:
                    if f"{{{{{field}}}}}" not in subj:
                        issues.append(f"Merge field {{{{{field}}}}} may be missing from email 1")
        else:
            issues.append(f"Only {len(seqs)} sequences found (expected {EXPECTED['sequences']})")
    except Exception as e:
        issues.append(f"Cannot fetch sequences: {e}")

    # Email accounts
    try:
        accounts = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/email-accounts")
        if isinstance(accounts, dict):
            accounts = accounts.get("data") or accounts.get("email_accounts") or []
        emails = [
            (a.get("from_email") or a.get("email") or "").lower()
            for a in (accounts if isinstance(accounts, list) else [])
        ]
        if EXPECTED["sender_email"] in emails:
            ok.append(f"Sender attached: {EXPECTED['sender_email']}")
        elif emails:
            issues.append(f"Sender mismatch — attached: {emails}, expected {EXPECTED['sender_email']}")
        else:
            issues.append(f"No sender attached — add {EXPECTED['sender_email']}")
    except Exception as e:
        issues.append(f"Cannot fetch email accounts: {e}")

    # Lead count (approx)
    try:
        leads = _get(api_key, f"/campaigns/{CAMPAIGN_ID}/leads?limit=1&offset=0")
        total = 0
        if isinstance(leads, dict):
            total = leads.get("total_leads") or leads.get("total") or len(leads.get("data") or [])
        if total and int(total) > 0:
            ok.append(f"Leads in campaign: {total}")
        else:
            issues.append("No leads imported yet — upload smartlead_us_upload_2026-07-02.csv")
    except Exception:
        issues.append("Could not verify lead count — check Leads tab in Smartlead UI")

    # Schedule hints from campaign object
    tz = campaign.get("timezone") or campaign.get("scheduler_cron_value") or ""
    if EXPECTED["timezone"] in str(tz) or "New_York" in str(tz):
        ok.append(f"Timezone looks US: {tz or 'America/New_York'}")
    elif tz:
        issues.append(f"Timezone may be wrong: {tz!r} (expected America/New_York)")

    if status.upper() in ("DRAFT", "DRAFTED", "PAUSED"):
        issues.append(f"Campaign status is {status} — activate after test send")
    elif status.upper() in ("ACTIVE", "START", "STARTED"):
        ok.append("Campaign is ACTIVE")

    issues.append("MANUAL: Send test email to yourself before going live")
    issues.append("MANUAL: Confirm max 5 new leads/day in Schedule settings")

    _print_report(ok, issues)


def _print_report(ok: list[str], issues: list[str]) -> None:
    print("PASS:")
    for x in ok:
        print(f"  ✓ {x}")
    print("\nCHECK / ACTION:")
    for x in issues:
        print(f"  • {x}")
    launch_ready = not any(
        "missing" in i.lower() or "mismatch" in i.lower() or "no leads" in i.lower() or "no sender" in i.lower()
        for i in issues
        if "MANUAL" not in i
    )
    print(f"\n{'READY FOR TEST SEND' if launch_ready else 'NOT READY — fix items above first'}")


if __name__ == "__main__":
    main()
