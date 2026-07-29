#!/usr/bin/env python3
"""Test Smartlead API connectivity. Usage: python3 scripts/test_smartlead_api.py [campaign_id]"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smartlead_client import api_request, explain_http_error, load_api_key, safe_error_message

DEFAULT_CAMPAIGN = "3607862"


def main() -> None:
    campaign_id = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CAMPAIGN).strip()
    key = load_api_key()

    print("=== Smartlead API test ===\n")
    if not key:
        print("FAIL: SMARTLEAD_API_KEY is empty in .env")
        raise SystemExit(1)
    print(f"Key loaded: yes ({len(key)} chars)\n")

    tests = [
        ("List campaigns", "GET", "/campaigns/"),
        (f"Campaign {campaign_id}", "GET", f"/campaigns/{campaign_id}"),
        (f"Sequences {campaign_id}", "GET", f"/campaigns/{campaign_id}/sequences"),
        (f"Email accounts {campaign_id}", "GET", f"/campaigns/{campaign_id}/email-accounts"),
    ]

    any_ok = False
    for label, method, path in tests:
        try:
            code, data = api_request(method, path, api_key=key)
        except Exception as e:
            print(f"{label} → ERROR")
            print(" ", safe_error_message(e))
            if "proxy" in str(e).lower():
                print("  Tip: unset HTTP_PROXY / HTTPS_PROXY in this terminal, then retry.")
            print()
            continue
        print(f"{label} → HTTP {code}")
        if code == 200:
            any_ok = True
            if isinstance(data, list):
                print(f"  ({len(data)} items)")
                if path == "/campaigns/" and data:
                    for c in data[:5]:
                        if isinstance(c, dict):
                            print(
                                f"  • {c.get('id')} | {c.get('status')} | {c.get('name')}"
                            )
            elif isinstance(data, dict):
                if "name" in data:
                    print(f"  name: {data.get('name')}")
                    print(f"  status: {data.get('status')}")
                else:
                    print(" ", json.dumps(data)[:400])
        else:
            print(" ", explain_http_error(code, data))
            if isinstance(data, (dict, list)):
                print(" ", json.dumps(data)[:400])
        print()

    if any_ok:
        print("OK — API access works. Run: python3 scripts/audit_smartlead_aesthetics_campaign.py")
        raise SystemExit(0)

    print("FAIL — API calls did not succeed. See messages above.")
    print("Manual launch still works: Smartlead → Campaign → Leads → Import CSV.")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
