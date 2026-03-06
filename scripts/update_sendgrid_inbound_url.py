#!/usr/bin/env python3
"""
Update SendGrid Inbound Parse destination URL via API (when the UI won't let you edit).
Usage: python3 scripts/update_sendgrid_inbound_url.py [hostname]
Default hostname: inbound.lumo22.com
New URL is always: https://lumo22.com/webhooks/sendgrid-inbound
"""
import os
import sys
import urllib.request
import urllib.error
import json

# Project root
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

def main():
    from dotenv import load_dotenv
    load_dotenv()

    from config import Config

    hostname = (sys.argv[1].strip() if len(sys.argv) > 1 else "inbound.lumo22.com")
    new_url = "https://lumo22.com/webhooks/sendgrid-inbound"
    api_key = (Config.SENDGRID_API_KEY or "").strip()
    if not api_key:
        print("ERROR: SENDGRID_API_KEY not set in .env")
        sys.exit(1)

    url = f"https://api.sendgrid.com/v3/user/webhooks/parse/settings/{hostname}"
    data = json.dumps({"url": new_url}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Updated Inbound Parse for hostname: {hostname}")
            print(f"  New destination URL: {new_url}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"SendGrid API error {e.code}: {e.reason}")
        print(body[:500] if body else "")
        sys.exit(1)

if __name__ == "__main__":
    main()
