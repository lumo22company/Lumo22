#!/usr/bin/env python3
"""Audit US aesthetics Smartlead campaign readiness (default 3607862)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smartlead_client import api_request, explain_http_error, load_api_key

CAMPAIGN_ID = "3607862"
EXPECTED_CTA = "https://www.lumo22.com/captions-sample"
EXPECTED_SENDER = "sophie@lumo22.com"


def main() -> None:
    cid = (sys.argv[1] if len(sys.argv) > 1 else CAMPAIGN_ID).strip()
    key = load_api_key()
    issues: list[str] = []
    ok: list[str] = []

    print(f"=== Aesthetics campaign audit ({cid}) ===\n")
    if not key:
        issues.append("SMARTLEAD_API_KEY missing in .env")
        _report(ok, issues)
        raise SystemExit(1)

    code, campaign = api_request("GET", f"/campaigns/{cid}", api_key=key)
    if code != 200:
        issues.append(explain_http_error(code, campaign))
        _report(ok, issues)
        raise SystemExit(1)

    name = campaign.get("name") or "?"
    status = campaign.get("status") or "?"
    ok.append(f"Campaign: {name!r}")
    ok.append(f"Status: {status}")
    if str(status).upper() in ("ACTIVE", "START", "STARTED"):
        ok.append("Campaign is ACTIVE")
    elif str(status).upper() in ("DRAFT", "PAUSED", "DRAFTED"):
        issues.append(f"Campaign is {status} — resume after test send")

    code, seqs = api_request("GET", f"/campaigns/{cid}/sequences", api_key=key)
    if code != 200:
        issues.append(f"Cannot load sequences: {explain_http_error(code, seqs)}")
    else:
        if isinstance(seqs, dict):
            seqs = seqs.get("sequences") or seqs.get("data") or []
        ok.append(f"Sequence steps: {len(seqs)}")
        if not seqs:
            issues.append("No email sequence configured")
        else:
            s1 = seqs[0]
            subj = s1.get("subject") or ""
            body = s1.get("email_body") or s1.get("body") or ""
            ok.append(f"Email 1 subject: {subj[:90]}")
            if EXPECTED_CTA in body:
                ok.append("Sample CTA in email 1")
            else:
                issues.append(f"Missing {EXPECTED_CTA} in email 1")
            for field in ("company_name", "personalization_line"):
                tag = "{{" + field + "}}"
                if tag not in body and tag not in subj:
                    issues.append(f"Missing merge field {tag}")

    code, acc = api_request("GET", f"/campaigns/{cid}/email-accounts", api_key=key)
    if code != 200:
        issues.append(f"Cannot load senders: {explain_http_error(code, acc)}")
    else:
        if isinstance(acc, dict):
            acc = acc.get("data") or acc.get("email_accounts") or []
        emails = [(a.get("from_email") or a.get("email") or "").lower() for a in acc]
        if EXPECTED_SENDER in emails:
            ok.append(f"Sender attached: {EXPECTED_SENDER}")
        elif emails:
            issues.append(f"Sender mismatch — attached: {emails}")
        else:
            issues.append(f"No sender attached — add {EXPECTED_SENDER}")

    code, leads = api_request("GET", f"/campaigns/{cid}/leads", api_key=key, params={"limit": 1, "offset": 0})
    if code != 200:
        issues.append(f"Cannot load leads: {explain_http_error(code, leads)}")
    else:
        total = 0
        if isinstance(leads, dict):
            total = int(leads.get("total_leads") or leads.get("total") or 0)
        ok.append(f"Leads in campaign: {total}")
        if total == 0:
            issues.append("No leads imported — upload smartlead_new_only_*.csv")

    issues.append("MANUAL: Send test email before going live")
    _report(ok, issues)


def _report(ok: list[str], issues: list[str]) -> None:
    print("PASS:")
    for x in ok:
        print(f"  ✓ {x}")
    print("\nCHECK:")
    for x in issues:
        print(f"  • {x}")
    blockers = [
        i
        for i in issues
        if "MANUAL" not in i
        and not i.startswith("Campaign is PAUSED")
        and not i.startswith("Campaign is DRAFT")
    ]
    print(f"\n{'READY FOR TEST SEND' if not blockers else 'FIX BLOCKERS ABOVE'}")


if __name__ == "__main__":
    main()
