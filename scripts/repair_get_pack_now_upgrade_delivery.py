#!/usr/bin/env python3
"""
Replay checkout email + intake copy + first-pack generation for an upgrade
checkout where get_pack_now=1 but checkout.session.completed never completed
in the app (e.g. order was backfilled from Stripe Session only).

Mirrors api/webhooks.py after _handle_captions_payment for subscription + get_pack_now:
  1. Optional: send subscription welcome prefilled (paid upgrade) or upgrade confirmation ($0 deferred).
  2. Copy intake from one-off (copy_from) onto subscription order; align platform/stories with order row.
  3. Run _run_generation_and_deliver (same as webhook thread).

Usage:
  python3 scripts/repair_get_pack_now_upgrade_delivery.py --session-id cs_test_...
  python3 scripts/repair_get_pack_now_upgrade_delivery.py --session-id cs_test_... --send-email
  python3 scripts/repair_get_pack_now_upgrade_delivery.py --session-id cs_test_... --deliver
  python3 scripts/repair_get_pack_now_upgrade_delivery.py --session-id cs_test_... --send-email --deliver

Default with both flags omitted: dry-run (prints plan only). Pass --send-email and/or --deliver to execute.

Requires: .env STRIPE_SECRET_KEY, Supabase, SendGrid (for email), AI keys (for delivery).
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from config import Config


def _sanitize_base_url(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    s = re.sub(r"[\x00-\x1f\x7f]", "", raw.strip())
    return s.rstrip("/").strip()


def _format_paid_amount(amount_total, currency: str) -> str:
    if amount_total is None:
        return ""
    try:
        amt = int(amount_total)
    except (TypeError, ValueError):
        return ""
    curr = (currency or "gbp").strip().lower()
    if curr == "usd":
        return f"${amt / 100:.2f}"
    if curr == "eur":
        return f"€{amt / 100:.2f}"
    if curr == "gbp":
        return f"£{amt / 100:.2f}"
    return f"{amt / 100:.2f} {curr.upper()}"


def _session_meta(session: dict) -> dict:
    m = session.get("metadata")
    if isinstance(m, dict):
        return m
    if m is not None and hasattr(m, "to_dict"):
        try:
            return m.to_dict()
        except Exception:
            pass
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-id", required=True, help="Stripe Checkout Session id")
    ap.add_argument("--send-email", action="store_true", help="Send checkout upgrade / welcome email")
    ap.add_argument("--deliver", action="store_true", help="Copy intake from one-off and run generation + PDF email")
    args = ap.parse_args()
    sid = (args.session_id or "").strip()
    if not sid.startswith("cs_"):
        print("ERROR: --session-id must be a Checkout Session id (cs_...)")
        sys.exit(1)

    if not (Config.STRIPE_SECRET_KEY or "").strip():
        print("ERROR: STRIPE_SECRET_KEY not set")
        sys.exit(1)

    import stripe
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
    full = stripe.checkout.Session.retrieve(sid, expand=["line_items", "customer_details", "customer"])
    session = full.to_dict() if hasattr(full, "to_dict") else dict(full)
    meta = _session_meta(session)
    product = (meta.get("product") or "").strip()
    if product != "captions_subscription":
        print(f"ERROR: session metadata product={product!r} expected captions_subscription")
        sys.exit(1)
    if str(meta.get("get_pack_now") or "").strip().lower() not in ("1", "true", "yes", "on"):
        print("ERROR: session does not have get_pack_now=1; this repair is for that flow only.")
        sys.exit(1)
    copy_from = (meta.get("copy_from") or "").strip()
    if not copy_from:
        print("ERROR: missing copy_from in session metadata")
        sys.exit(1)

    svc = CaptionOrderService()
    order = svc.get_by_stripe_session_id(sid)
    if not order:
        print(f"ERROR: no caption_orders row with stripe_session_id={sid!r}")
        sys.exit(1)
    one_off = svc.get_by_token(copy_from)
    if not one_off:
        print(f"ERROR: no one-off order for token copy_from={copy_from!r}")
        sys.exit(1)
    intake = one_off.get("intake") if isinstance(one_off.get("intake"), dict) else None
    if not intake:
        print("ERROR: one-off order has no intake; cannot copy for delivery")
        sys.exit(1)

    oid = str(order.get("id") or "").strip()
    customer_email = (order.get("customer_email") or "").strip()
    amount_total = session.get("amount_total")
    upgraded_from_oneoff = bool((order.get("upgraded_from_token") or copy_from).strip())
    is_trial_upgrade = upgraded_from_oneoff and (
        amount_total is None or (isinstance(amount_total, (int, float)) and int(amount_total) == 0)
    )

    base = _sanitize_base_url(Config.BASE_URL or "")
    if not base or not base.startswith("http"):
        base = "https://lumo-22-production.up.railway.app"
    safe_token = str(order.get("token") or "").strip()
    intake_url = f"{base}/captions-intake?t={safe_token}&copy_from={copy_from}"

    print("Plan:")
    print(f"  order_id={oid} token=…{safe_token[-6:]} email={customer_email!r}")
    print(f"  copy_from={copy_from} one_off_id={one_off.get('id')}")
    print(f"  amount_total={amount_total} → email kind={'upgrade_confirmation (deferred)' if is_trial_upgrade else 'welcome_prefilled (paid)'}")
    print(f"  intake_url={intake_url[:80]}…")

    if not args.send_email and not args.deliver:
        print("\nDry-run. Pass --send-email and/or --deliver to execute.")
        sys.exit(0)

    if args.send_email:
        notif = NotificationService()
        if is_trial_upgrade:
            from datetime import datetime, timedelta, timezone

            first_charge_date_str = None
            raw = one_off.get("delivered_at") or one_off.get("updated_at") or one_off.get("created_at")
            if raw:
                try:
                    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                    if getattr(dt, "tzinfo", None) is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    first_charge_date_str = (dt + timedelta(days=30)).strftime("%d %B %Y")
                except Exception:
                    pass
            ok = notif.send_subscription_upgrade_confirmation_email(
                customer_email, intake_url, first_charge_date_str, order=order
            )
            print("send_subscription_upgrade_confirmation_email:", "OK" if ok else "FAILED")
        else:
            amount_paid = _format_paid_amount(amount_total, (order.get("currency") or "gbp"))
            ok = notif.send_subscription_welcome_prefilled_email(
                customer_email, intake_url, order=order, amount_paid=amount_paid
            )
            print("send_subscription_welcome_prefilled_email:", "OK" if ok else "FAILED")
        if not ok:
            sys.exit(1)

    if args.deliver:
        from api.captions_routes import _run_generation_and_deliver

        synced_intake = dict(intake)
        selected = (order.get("selected_platforms") or "").strip()
        if selected:
            synced_intake["platform"] = selected
        synced_intake["include_stories"] = bool(order.get("include_stories"))
        svc.save_intake(oid, synced_intake)
        print("Copied intake from one-off onto subscription order; starting generation…")
        result = _run_generation_and_deliver(oid)
        print("_run_generation_and_deliver:", result)


if __name__ == "__main__":
    main()
