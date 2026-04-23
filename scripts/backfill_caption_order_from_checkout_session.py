#!/usr/bin/env python3
"""
Create or patch a caption_orders row from a Stripe Checkout Session (test or live).

Use when checkout.session.completed never reached the app: no row with this
stripe_session_id exists, but Stripe has customer + subscription on the session.

  python3 scripts/backfill_caption_order_from_checkout_session.py --session-id cs_test_...

  python3 scripts/backfill_caption_order_from_checkout_session.py --session-id cs_test_... --apply

Requires: .env with STRIPE_SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from api.captions_routes import seed_intake_business_from_stripe_metadata
from config import Config
from services.caption_order_service import CaptionOrderService


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-id", required=True, help="Stripe Checkout Session id cs_...")
    p.add_argument("--apply", action="store_true", help="Create or update; default is dry-run")
    args = p.parse_args()
    sid = (args.session_id or "").strip()
    if not sid.startswith("cs_"):
        print("ERROR: --session-id must look like cs_test_... or cs_live_...")
        sys.exit(1)

    if not (Config.STRIPE_SECRET_KEY or "").strip():
        print("ERROR: STRIPE_SECRET_KEY not set")
        sys.exit(1)

    import stripe

    stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
    mode = "live" if stripe.api_key.startswith("sk_live") else "test"
    print(f"Stripe mode: {mode}\n")

    s = stripe.checkout.Session.retrieve(sid)
    meta = dict(s.get("metadata") or {})
    cus = (s.get("customer") or "").strip()
    sub = (s.get("subscription") or "").strip()
    cd = s.get("customer_details") or {}
    email = (cd.get("email") or s.get("customer_email") or "").strip().lower()
    if not email or "@" not in email:
        print("ERROR: Session has no customer email")
        sys.exit(1)

    try:
        platforms_count = max(1, int(meta.get("platforms") or 1))
    except (TypeError, ValueError):
        platforms_count = 1
    selected = (meta.get("selected_platforms") or "").strip() or None
    stories = str(meta.get("include_stories") or "").lower() in ("1", "true", "yes")
    curr = (s.get("currency") or "gbp").strip().lower()
    if curr not in ("gbp", "usd", "eur"):
        curr = "gbp"
    copy_from = (meta.get("copy_from") or "").strip() or None
    is_sub = (s.get("mode") or "").strip() == "subscription"
    upgraded = copy_from if (copy_from and is_sub) else None

    svc = CaptionOrderService()
    existing = svc.get_by_stripe_session_id(sid)

    if existing:
        print(f"Existing order id={existing.get('id')} token={existing.get('token')!r}")
        updates = {}
        if cus and not (existing.get("stripe_customer_id") or "").strip():
            updates["stripe_customer_id"] = cus
        if sub and not (existing.get("stripe_subscription_id") or "").strip():
            updates["stripe_subscription_id"] = sub
        if upgraded and not (existing.get("upgraded_from_token") or "").strip():
            updates["upgraded_from_token"] = upgraded
        if not updates:
            print("No missing Stripe fields to patch.")
        else:
            if args.apply:
                svc.update(str(existing["id"]), updates)
                print("Patched:", updates)
            else:
                print("Dry-run would patch:", updates)
        order = svc.get_by_id(str(existing["id"])) if existing.get("id") else existing
    else:
        print("No caption_orders row for this session — would create_order with:")
        print(f"  email={email!r} stripe_session_id={sid!r}")
        print(f"  stripe_customer_id={cus!r} stripe_subscription_id={sub!r}")
        print(f"  platforms_count={platforms_count} selected_platforms={selected!r}")
        print(f"  include_stories={stories} currency={curr} upgraded_from_token={upgraded!r}")
        if not args.apply:
            print("\nPass --apply to insert the row and seed intake from metadata.")
            sys.exit(0)
        order = svc.create_order(
            customer_email=email,
            stripe_session_id=sid,
            stripe_customer_id=cus or None,
            stripe_subscription_id=sub or None,
            platforms_count=platforms_count,
            selected_platforms=selected,
            include_stories=stories,
            currency=curr,
            upgraded_from_token=upgraded,
        )
        print(f"Created order id={order.get('id')} token={order.get('token')!r}")

    if args.apply:
        order = seed_intake_business_from_stripe_metadata(svc, order, meta)
        ib = (order.get("intake") or {}).get("business_name") if isinstance(order.get("intake"), dict) else None
        print("After intake seed, intake.business_name:", ib)


if __name__ == "__main__":
    main()
