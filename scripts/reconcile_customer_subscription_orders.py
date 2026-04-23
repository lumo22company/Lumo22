#!/usr/bin/env python3
"""
Reconcile Stripe active subscription(s) with caption_orders for one customer.

Typical gap: subscription exists in Stripe (customer + sub_*) but the Lumo row
never received stripe_customer_id / stripe_subscription_id (webhook miss, etc.).

Steps:
  1. Resolve Stripe customer (--customer-id or search by --email).
  2. List active subscriptions for that customer.
  3. For each subscription, find the caption_orders row by stripe_subscription_id,
     or by checkout Session id (Session.list → get_by_stripe_session_id).
  4. With --apply, PATCH missing stripe_customer_id / stripe_subscription_id on that row.

Optional cleanup:
  --clear-upgraded-from-if-no-sub ORDER_UUID
      Sets upgraded_from_token to NULL only when stripe_subscription_id is empty
      (stale shells with impossible copy_from links).

Run from project root:
  python3 scripts/reconcile_customer_subscription_orders.py \\
    --email sophieoverment@gmail.com --customer-id cus_UO6YQvgQbCUw5n

  python3 scripts/reconcile_customer_subscription_orders.py ... --apply

Requires: .env with STRIPE_SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from config import Config
from services.caption_order_service import CaptionOrderService


def _require_config() -> None:
    if not (Config.SUPABASE_URL or "").strip():
        print("ERROR: SUPABASE_URL not set.")
        sys.exit(1)
    if not ((Config.SUPABASE_SERVICE_ROLE_KEY or "").strip() or (Config.SUPABASE_KEY or "").strip()):
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set.")
        sys.exit(1)
    if not (Config.STRIPE_SECRET_KEY or "").strip():
        print("ERROR: STRIPE_SECRET_KEY not set.")
        sys.exit(1)


def _resolve_customer_id(stripe_module, email: str, explicit_cus: str | None) -> str:
    if explicit_cus and explicit_cus.startswith("cus_"):
        return explicit_cus.strip()
    if not email or "@" not in email:
        print("ERROR: provide --customer-id cus_... or --email for Stripe customer search.")
        sys.exit(1)
    found = stripe_module.Customer.list(email=email.lower().strip(), limit=5)
    ids = [(c.id, c.get("email") or "") for c in (found.data or [])]
    if not ids:
        print(f"ERROR: No Stripe customer with email={email!r}. Pass --customer-id explicitly.")
        sys.exit(1)
    if len(ids) > 1:
        print(f"Multiple Stripe customers for {email!r}:")
        for cid, em in ids:
            print(f"  {cid}  email={em!r}")
        print("Re-run with --customer-id cus_...")
        sys.exit(1)
    return ids[0][0]


def _sessions_for_subscription(stripe_module, customer_id: str, subscription_id: str):
    """
    Return checkout sessions for this subscription (newest first).
    Prefer Session.list(subscription=...) — works when customer filter would miss old sessions.
    """
    out = []
    try:
        by_sub = stripe_module.checkout.Session.list(subscription=subscription_id, limit=20)
        for s in by_sub.auto_paging_iter():
            if (s.get("mode") or "") == "subscription":
                out.append(s)
    except Exception as e:
        print(f"  (Session.list(subscription=…) failed: {e!r}; falling back to customer filter.)")
    if not out:
        sessions = stripe_module.checkout.Session.list(customer=customer_id, limit=100)
        for s in sessions.auto_paging_iter():
            if (s.get("mode") or "") != "subscription":
                continue
            sub = (s.get("subscription") or "").strip()
            if sub == subscription_id:
                out.append(s)
    out.sort(key=lambda x: int(x.get("created") or 0), reverse=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="", help="Customer email (Stripe + caption_orders context)")
    parser.add_argument("--customer-id", default="", dest="customer_id", help="Stripe customer id cus_...")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing stripe_customer_id / stripe_subscription_id to caption_orders",
    )
    parser.add_argument(
        "--clear-upgraded-from-if-no-sub",
        default="",
        metavar="ORDER_UUID",
        help="Set upgraded_from_token NULL on this order id only if stripe_subscription_id is empty",
    )
    args = parser.parse_args()

    _require_config()

    import stripe

    sk = Config.STRIPE_SECRET_KEY.strip()
    stripe.api_key = sk
    mode = "live" if sk.startswith("sk_live") else ("test" if sk.startswith("sk_test") else "unknown")
    print(f"Stripe API mode: {mode} (key prefix {sk[:12]}…)\n")

    email = (args.email or "").strip().lower()
    cus = _resolve_customer_id(stripe, email, (args.customer_id or "").strip() or None)

    svc = CaptionOrderService()

    subs = stripe.Subscription.list(customer=cus, status="active", limit=20)
    if not subs.data:
        print(f"No active subscriptions for {cus}.")
        subs_all = stripe.Subscription.list(customer=cus, status="all", limit=5)
        if subs_all.data:
            print("Recent non-active subscriptions (for reference):")
            for s in subs_all.data[:5]:
                print(f"  {s.id} status={s.status!r} created={s.created}")
        sys.exit(0)

    print(f"Stripe customer: {cus}")
    if email:
        print(f"Email (arg):   {email}")

    if args.clear_upgraded_from_if_no_sub.strip():
        oid = args.clear_upgraded_from_if_no_sub.strip()
        row = svc.get_by_id(oid)
        if not row:
            print(f"ERROR: No caption_orders row for id={oid}")
            sys.exit(1)
        if (row.get("stripe_subscription_id") or "").strip():
            print(
                f"Refusing to clear upgraded_from_token: order {oid[:8]}… has stripe_subscription_id set."
            )
            sys.exit(1)
        print(
            f"Order {oid[:8]}… token={row.get('token')!r} upgraded_from_token="
            f"{(row.get('upgraded_from_token') or '')!r} stripe_subscription_id empty — OK to clear."
        )
        if args.apply:
            svc.update(oid, {"upgraded_from_token": None})
            print("Applied: upgraded_from_token → NULL")
        else:
            print("Dry-run: pass --apply to clear upgraded_from_token.")
        # Continue to subscription reconciliation below

    orders_ctx = []
    if email and "@" in email:
        try:
            orders_ctx = svc.get_by_customer_email_including_stripe_customer(email) or []
        except Exception as e:
            print(f"Warning: could not load orders by email: {e!r}")

    print(f"\nCaption orders for login/email context: {len(orders_ctx)} row(s)")
    for o in orders_ctx[:15]:
        print(
            f"  id={str(o.get('id'))[:8]}… created={o.get('created_at')} status={o.get('status')!r} "
            f"token=…{str(o.get('token') or '')[-6:]!r} "
            f"cus={(o.get('stripe_customer_id') or '')[:16] or '—'}… "
            f"sub={(o.get('stripe_subscription_id') or '')[:16] or '—'}… "
            f"biz={(o.get('business_name') or '')[:32]!r}"
        )
    if len(orders_ctx) > 15:
        print(f"  … and {len(orders_ctx) - 15} more")

    for sub in subs.data:
        sub_id = sub.id
        print(f"\n--- Active subscription {sub_id} ---")
        db_by_sub = svc.get_by_stripe_subscription_id(sub_id)
        if db_by_sub:
            print(
                f"DB match by stripe_subscription_id: order id={db_by_sub.get('id')} "
                f"token=…{str(db_by_sub.get('token') or '')[-8:]}"
            )
            missing = {}
            if not (db_by_sub.get("stripe_customer_id") or "").strip():
                missing["stripe_customer_id"] = cus
            if not (db_by_sub.get("stripe_subscription_id") or "").strip():
                missing["stripe_subscription_id"] = sub_id
            if missing:
                print(f"  Row exists but missing: {list(missing.keys())}")
                if args.apply:
                    svc.update(str(db_by_sub["id"]), missing)
                    print(f"  Applied update on {str(db_by_sub['id'])[:8]}…")
                else:
                    print("  Dry-run: pass --apply to write these fields.")
            continue

        sessions = _sessions_for_subscription(stripe, cus, sub_id)
        if not sessions:
            print("No Checkout Session found for this customer+subscription (list may be truncated).")
            continue
        s = sessions[0]
        csid = s.id
        print(f"Using checkout session {csid} (created={s.get('created')})")
        db_by_session = svc.get_by_stripe_session_id(csid)
        if not db_by_session:
            print(
                f"No caption_orders row with stripe_session_id={csid!r}. "
                "Webhook / intake-link may not have created the row; fix in Stripe + DB manually or replay webhook."
            )
            continue
        print(
            f"DB match by stripe_session_id: order id={db_by_session.get('id')} "
            f"email={db_by_session.get('customer_email')!r}"
        )
        updates = {}
        if not (db_by_session.get("stripe_customer_id") or "").strip():
            updates["stripe_customer_id"] = cus
        if not (db_by_session.get("stripe_subscription_id") or "").strip():
            updates["stripe_subscription_id"] = sub_id
        if not updates:
            print("  Stripe ids already present; nothing to do.")
            continue
        print(f"  Would set: {updates}")
        if args.apply:
            svc.update(str(db_by_session["id"]), updates)
            print(f"  Applied on order {str(db_by_session['id'])[:8]}…")
        else:
            print("  Dry-run: pass --apply to write.")


if __name__ == "__main__":
    main()
