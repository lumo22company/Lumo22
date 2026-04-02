#!/usr/bin/env python3
"""
Send a sample order-confirmed + intake email (real SendGrid send, for preview).
Requires SENDGRID_API_KEY (and related config) in .env.

Usage:
  python3 scripts/send_sample_order_confirmation_email.py --to you@example.com
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send sample order confirmation + intake email")
    parser.add_argument(
        "--to",
        default="skoverment@gmail.com",
        help="Recipient email address",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    from services.notifications import NotificationService

    # Rich mock checkout: line items come from order; totals from session (promo + tax).
    order = {
        "platforms_count": 2,
        "selected_platforms": "Instagram, LinkedIn",
        "include_stories": True,
        "currency": "gbp",
        "stripe_subscription_id": "",
        "intake": {"business_name": "Demo Bakery Co."},
    }
    session = {
        "id": "cs_sample_preview",
        "currency": "gbp",
        "amount_total": 19885,
        "amount_subtotal": 20500,
        "total_details": {
            "amount_discount": 2000,
            "amount_tax": 1385,
        },
        "discounts": [{"promotion_code": {"code": "FRIEND20"}}],
    }
    intake_url = "https://www.lumo22.com/captions-intake?t=sample-preview-token"

    notif = NotificationService()
    ok = notif.send_intake_link_email(args.to, intake_url, order, session=session)
    if ok:
        print(f"Sent sample order confirmation email to {args.to}")
        return 0
    print("Send failed (check SendGrid logs / API key).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
