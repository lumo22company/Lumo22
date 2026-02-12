#!/usr/bin/env python3
"""
Backfill stripe_customer_id and stripe_subscription_id for existing caption orders.
Orders with stripe_session_id but missing stripe_customer_id get IDs from Stripe API.
Run from project root: python3 scripts/backfill_stripe_ids.py
Requires: .env with STRIPE_SECRET_KEY, SUPABASE_URL, SUPABASE_KEY
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from config import Config
from services.caption_order_service import CaptionOrderService
from supabase import create_client


def main():
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)

    import stripe
    stripe.api_key = secret

    svc = CaptionOrderService()
    # Get all orders with stripe_session_id
    result = svc.client.table("caption_orders").select(
        "id, stripe_session_id, stripe_customer_id, stripe_subscription_id, customer_email"
    ).execute()

    orders = result.data or []
    to_backfill = [o for o in orders if o.get("stripe_session_id") and not o.get("stripe_customer_id")]

    if not to_backfill:
        print("No orders need backfill. All orders with stripe_session_id already have stripe_customer_id.")
        return

    print(f"Found {len(to_backfill)} order(s) to backfill.")

    for order in to_backfill:
        sid = order.get("stripe_session_id")
        oid = order.get("id")
        email = order.get("customer_email", "?")
        try:
            session = stripe.checkout.Session.retrieve(sid)
            cid = (session.get("customer") or "").strip() or None
            sub_id = (session.get("subscription") or "").strip() or None
            if cid or sub_id:
                updates = {}
                if cid:
                    updates["stripe_customer_id"] = cid
                if sub_id:
                    updates["stripe_subscription_id"] = sub_id
                if updates:
                    svc.update(oid, updates)
                    print(f"  OK: {email} — customer_id={cid[:20] if cid else '—'}... sub={sub_id[:20] if sub_id else '—'}...")
            else:
                print(f"  Skip: {email} — session has no customer/subscription (one-off payment?)")
        except Exception as e:
            print(f"  ERROR: {email} — {e}")

    print("Done.")


if __name__ == "__main__":
    main()
