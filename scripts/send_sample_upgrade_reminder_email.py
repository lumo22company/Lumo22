#!/usr/bin/env python3
"""
Send a one-off → subscription upgrade reminder (same template as production cron).
Requires SENDGRID_API_KEY and BASE_URL (or defaults) in .env.

Usage:
  python3 scripts/send_sample_upgrade_reminder_email.py --to you@example.com --token YOUR_ORDER_TOKEN \\
    --business-name "Northwind Plant Lab"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send sample one-off upgrade reminder email")
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--token", required=True, help="One-off order token (from caption_orders)")
    parser.add_argument("--business-name", default="", help="Business name for subject/body (optional)")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    from config import Config
    from services.notifications import NotificationService

    base = (getattr(Config, "BASE_URL", None) or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://www.lumo22.com"
    upgrade_url = f"{base}/captions-intake?" + urlencode({"t": args.token.strip(), "edit": "1"})
    unsubscribe_url = f"{base}/api/captions-upgrade-reminder-unsubscribe?t={quote(args.token.strip(), safe='')}"

    notif = NotificationService()
    ok = notif.send_one_off_upgrade_reminder_email(
        to_email=args.to.strip(),
        upgrade_url=upgrade_url,
        unsubscribe_url=unsubscribe_url,
        business_name=(args.business_name or "").strip() or None,
    )
    if ok:
        print(f"Sent upgrade reminder to {args.to}")
        print(f"  upgrade_url={upgrade_url}")
        return 0
    print("Send failed (check SendGrid / FROM_EMAIL in .env).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
