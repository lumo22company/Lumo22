#!/usr/bin/env python3
"""
Create Smartlead 'US Hiring SMM — Job intent' campaign via API (no lead import).

Uses sophie@lumo22.com (attach manually or pass --sophie-email-account-id).

Requires SMARTLEAD_API_KEY in .env (Smartlead → Settings → API).

Usage:
  python3 scripts/setup_smartlead_jobs_campaign_us.py
  python3 scripts/setup_smartlead_jobs_campaign_us.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"
CAMPAIGN_NAME = "US Hiring SMM — Job intent"

EMAIL_1_SUBJECT = "{{company_name}} — before the {{job_title}} hire?"
EMAIL_1_BODY = """Hi,

{{personalization_line}}

Most teams I talk to post for a {{job_title}} when the real bottleneck is content — captions and Stories that sound like them, every week, without another person to manage.

If that's you, I can send 3 free captions in {{company_name}}'s voice. Two-minute form, no card, in your inbox: https://www.lumo22.com/captions-sample

Worth a look before you narrow down candidates?

Sophie

%signature%"""

EMAIL_2_SUBJECT = "Re: {{company_name}} {{job_title}}"
EMAIL_2_BODY = """Hi,

Quick follow-up — hiring usually takes 4–8 weeks. Posting can't pause that long.

A lot of businesses bridge the gap with done-for-you captions (30 days mapped out, your tone) while the role is still open — cheaper than a hire, faster than agency.

If you want to see the quality first: 3 free captions, same form, no catch: https://www.lumo22.com/captions-sample

Sophie

%signature%"""

EMAIL_3_SUBJECT = "Close the loop?"
EMAIL_3_BODY = """Hi,

Last note from me on this.

If 3 free captions for {{company_name}} would help while you're filling the {{job_title}} role: https://www.lumo22.com/captions-sample

If not useful, reply "stop" and I won't follow up again.

Sophie

%signature%"""


def _req(api_key: str, method: str, path: str, body: dict | None = None) -> dict | list:
    q = urllib.parse.urlencode({"api_key": api_key})
    url = f"{BASE}{path}?{q}" if "?" not in path else f"{BASE}{path}&{q}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _html_body(text: str) -> str:
    parts = []
    for line in text.splitlines():
        if line.strip() == "":
            parts.append("<br><br>")
        else:
            parts.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            parts.append("<br>")
    return "".join(parts)


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--sophie-email-account-id",
        type=int,
        default=18240835,
        help="Smartlead email account ID for sophie@lumo22.com",
    )
    args = ap.parse_args()

    api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Missing SMARTLEAD_API_KEY in .env\n"
            "Smartlead → Settings → API → copy key, then re-run."
        )

    if args.dry_run:
        print(json.dumps({"campaign_name": CAMPAIGN_NAME, "sequences": 3}, indent=2))
        return

    created = _req(api_key, "POST", "/campaigns/create", {"name": CAMPAIGN_NAME})
    campaign_id = created.get("id") or created.get("campaign", {}).get("id")
    if not campaign_id:
        raise SystemExit(f"Unexpected create response: {created}")
    print(f"Created campaign {campaign_id}: {CAMPAIGN_NAME}")

    sequences = {
        "sequences": [
            {
                "id": None,
                "seq_number": 1,
                "subject": EMAIL_1_SUBJECT,
                "email_body": _html_body(EMAIL_1_BODY),
                "seq_delay_details": {"delay_in_days": 0},
            },
            {
                "id": None,
                "seq_number": 2,
                "subject": EMAIL_2_SUBJECT,
                "email_body": _html_body(EMAIL_2_BODY),
                "seq_delay_details": {"delay_in_days": 3},
            },
            {
                "id": None,
                "seq_number": 3,
                "subject": EMAIL_3_SUBJECT,
                "email_body": _html_body(EMAIL_3_BODY),
                "seq_delay_details": {"delay_in_days": 5},
            },
        ]
    }
    _req(api_key, "POST", f"/campaigns/{campaign_id}/sequences", sequences)
    print("Added 3-email sequence (v2, US / Sophie)")

    schedule = {
        "timezone": "America/New_York",
        "days_of_the_week": [1, 2, 3, 4, 5],
        "start_hour": "09:30",
        "end_hour": "17:00",
        "min_time_btw_emails": 5,
        "max_new_leads_per_day": 5,
    }
    try:
        _req(api_key, "POST", f"/campaigns/{campaign_id}/schedule", schedule)
        print("Set US schedule (5 leads/day, America/New_York)")
    except urllib.error.HTTPError as e:
        print(f"Schedule API note: HTTP {e.code} — set schedule manually in UI")

    if args.sophie_email_account_id:
        try:
            _req(
                api_key,
                "POST",
                f"/campaigns/{campaign_id}/email-accounts",
                {"email_account_ids": [args.sophie_email_account_id]},
            )
            print(f"Attached email account {args.sophie_email_account_id}")
        except urllib.error.HTTPError as e:
            print(f"Email account attach note: HTTP {e.code} — attach sophie@ manually")

    out = ROOT / "exports" / "smartlead_jobs_campaign_us_created.json"
    out.write_text(
        json.dumps(
            {
                "campaign_id": campaign_id,
                "campaign_name": CAMPAIGN_NAME,
                "status": "DRAFTED",
                "sender": "sophie@lumo22.com",
                "import_csv_when_ready": "exports/smartlead_new_only_jobs_smm_intent_us_*.csv",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    print("\nNext: attach sophie@lumo22.com if needed, send test email, scrape US leads, then import.")


if __name__ == "__main__":
    main()
