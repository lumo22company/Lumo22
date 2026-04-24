#!/usr/bin/env python3
"""
Backfill a missing caption_orders row when Stripe has an active subscription but Lumo never
created the order (e.g. checkout.session.completed exited before create_order because email was
missing from the Session object — fixed in api/webhooks.py for future events).

Finds the Checkout Session for this subscription (via Session.list(customer=...)), then runs
the same _handle_captions_payment() as the webhook. For upgrade + get_pack_now, also runs
try_schedule_upgrade_get_pack_now_delivery() like checkout.session.completed.

Usage (requires .env with STRIPE_SECRET_KEY + Supabase service role / keys like production):

  # Inspect only
  python3 scripts/backfill_caption_order_from_stripe_subscription.py \\
    --subscription-id sub_1TPhV0A6qx3WwR4sKL3qvq4C

  # Create row + emails + get_pack_now delivery (if applicable)
  python3 scripts/backfill_caption_order_from_stripe_subscription.py \\
    --subscription-id sub_1TPhV0A6qx3WwR4sKL3qvq4C --execute

If listing sessions does not find a match (rare), pass the Checkout Session id explicitly:

  python3 scripts/backfill_caption_order_from_stripe_subscription.py --session-id cs_... --execute
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def _sub_id_from_session_obj(s) -> str:
    raw = getattr(s, "subscription", None)
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return (raw.get("id") or "").strip()
    rid = getattr(raw, "id", None)
    return str(rid).strip() if rid else ""


def _customer_id_from_subscription(sub) -> str:
    cust = getattr(sub, "customer", None)
    if cust is None:
        return ""
    if isinstance(cust, str):
        return cust.strip()
    if isinstance(cust, dict):
        return (cust.get("id") or "").strip()
    return str(getattr(cust, "id", "") or "").strip()


def _normalize_checkout_session_expandables(d: dict) -> dict:
    """Session.retrieve(expand=['customer']) nests customer/subscription as dicts; coerce to id strings."""
    if not isinstance(d, dict):
        return d
    out = dict(d)
    c = out.get("customer")
    if isinstance(c, dict) and (c.get("id") or "").strip():
        out["customer"] = (c.get("id") or "").strip()
    s = out.get("subscription")
    if isinstance(s, dict) and (s.get("id") or "").strip():
        out["subscription"] = (s.get("id") or "").strip()
    return out


def find_checkout_session_for_subscription(stripe_module, subscription_id: str):
    """Return expanded Checkout Session dict for subscription mode checkout that created this sub."""
    sub = stripe_module.Subscription.retrieve(subscription_id, expand=["customer"])
    cust_id = _customer_id_from_subscription(sub)
    if not cust_id.startswith("cus_"):
        raise SystemExit(f"No Stripe customer id on subscription {subscription_id!r}")

    sessions = stripe_module.checkout.Session.list(customer=cust_id, limit=100)
    for s in sessions.auto_paging_iter():
        if (getattr(s, "mode", None) or "") != "subscription":
            continue
        if _sub_id_from_session_obj(s) != subscription_id:
            continue
        full = stripe_module.checkout.Session.retrieve(
            s.id,
            expand=["line_items", "customer_details", "customer"],
        )
        return full.to_dict() if hasattr(full, "to_dict") else dict(full)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subscription-id", default="", help="Stripe subscription id (sub_...)")
    ap.add_argument("--session-id", default="", help="Checkout Session id (cs_...) if known")
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Run _handle_captions_payment and get_pack_now delivery; default is dry-run",
    )
    args = ap.parse_args()
    sub_id = (args.subscription_id or "").strip()
    session_id = (args.session_id or "").strip()

    if not session_id and not sub_id:
        ap.error("Provide --subscription-id and/or --session-id")

    if not (os.getenv("STRIPE_SECRET_KEY") or "").strip():
        print("ERROR: STRIPE_SECRET_KEY not set (load .env or export it).")
        sys.exit(1)

    import stripe

    from config import Config

    stripe.api_key = (Config.STRIPE_SECRET_KEY or "").strip()

    if session_id:
        if not session_id.startswith("cs_"):
            print("ERROR: --session-id must start with cs_")
            sys.exit(1)
        full = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items", "customer_details", "customer"],
        )
        session_dict = full.to_dict() if hasattr(full, "to_dict") else dict(full)
        print(f"Loaded Checkout Session {session_id}")
    else:
        session_dict = find_checkout_session_for_subscription(stripe, sub_id)
        if not session_dict:
            print(
                f"ERROR: No subscription-mode Checkout Session found for customer of {sub_id!r}.\n"
                "Open Stripe Dashboard → find the paid invoice → copy the Checkout Session id (cs_…) "
                "and re-run with --session-id cs_..."
            )
            sys.exit(1)
        print(f"Found Checkout Session {(session_dict.get('id') or '')!r} for subscription {sub_id!r}")

    session_dict = _normalize_checkout_session_expandables(session_dict)

    meta = session_dict.get("metadata") or {}
    print("metadata:", dict(meta) if isinstance(meta, dict) else meta)
    print("mode:", session_dict.get("mode"), "payment_status:", session_dict.get("payment_status"))
    print("subscription:", session_dict.get("subscription"))

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to create caption_orders + send emails + get_pack_now delivery.")
        return

    from api.webhooks import _handle_captions_payment
    from services.caption_order_service import CaptionOrderService
    from api.captions_routes import try_schedule_upgrade_get_pack_now_delivery

    print("\nRunning _handle_captions_payment…")
    _handle_captions_payment(session_dict)

    sid = (session_dict.get("id") or "").strip()
    order_service = CaptionOrderService()
    order = order_service.get_by_stripe_session_id(sid) if sid else None
    if not order:
        print("ERROR: Order still missing after _handle_captions_payment. Check Railway logs and Stripe metadata.")
        sys.exit(1)
    print(f"Order id={order.get('id')!r} token=…{(order.get('token') or '')[-8:]!r} status={order.get('status')!r}")

    meta_d = session_dict.get("metadata") or {}
    if isinstance(meta_d, dict) and str(meta_d.get("get_pack_now") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        print("Running try_schedule_upgrade_get_pack_now_delivery…")
        try_schedule_upgrade_get_pack_now_delivery(
            order_service,
            order,
            session_dict,
            log_prefix="[backfill_subscription]",
        )
    else:
        print("Not a get_pack_now checkout; skipping immediate delivery helper.")

    print("\nDone. Verify caption_orders in Supabase and check email / delivery logs.")


if __name__ == "__main__":
    main()
