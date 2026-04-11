#!/usr/bin/env python3
"""
Configure Stripe Customer Portal: enable subscription management, cancel, payment method update.
Run from project root: python3 scripts/configure_stripe_portal.py
Requires: .env with STRIPE_SECRET_KEY, BASE_URL

Cancellation behaviour (verify after running — Dashboard → Settings → Billing → Customer portal,
or run this script and confirm success):

- **Immediate cancel:** `subscription_cancel.mode` is **immediately** (not at_period_end). Matches
  `/api/captions/cancel-subscription` (`Subscription.delete` with `prorate=False`).

- **No proration credit on cancel:** `subscription_cancel.proration_behavior` is **none**. Otherwise
  Stripe adds invoice lines like “Unused time on …” (credits for prepaid period), which conflicts with
  terms that do not refund or credit unused time on cancellation.

- **No automatic card refund:** Cancelling does **not** refund the last charge by default. Refunds only
  happen if you manually refund in Stripe. Proration credits are separate from manual refunds.

- **Stripe’s cancel screen wording** is **fixed by Stripe** — we can’t edit it in our app. Clearer context
  is on the account page next to **Manage billing**.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    base = (os.getenv("BASE_URL", "") or "").strip().rstrip("/")
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    if not base:
        print("ERROR: BASE_URL not set in .env")
        sys.exit(1)
    if not base.startswith("http"):
        base = "https://" + base

    import stripe
    stripe.api_key = secret

    return_url = f"{base}/account"

    # List existing configs
    configs = stripe.billing_portal.Configuration.list(limit=10)
    default = next((c for c in configs.data if getattr(c, "is_default", False)), None)
    config = default or (configs.data[0] if configs.data else None)

    params = {
        "business_profile": {
            "headline": "Lumo 22 — Manage your subscription",
            "privacy_policy_url": f"{base}/terms",
            "terms_of_service_url": f"{base}/terms",
        },
        "default_return_url": return_url,
        "features": {
            "customer_update": {"enabled": True, "allowed_updates": ["email"]},
            # Invoice history on: customers can download past invoices in the portal. (Stripe does not offer
            # hiding invoices only on the cancel flow — portal features are global.)
            "invoice_history": {"enabled": True},
            "payment_method_update": {"enabled": True},
            # "immediately" matches /api/captions/cancel-subscription (Subscription.delete) and terms
            # ("cancellation takes effect immediately"). "at_period_end" shows Stripe copy like
            # "still available until [date]" which does not match immediate cancellation.
            "subscription_cancel": {
                "enabled": True,
                "mode": "immediately",
                "proration_behavior": "none",
                "cancellation_reason": {"enabled": True},
            },
            "subscription_update": {"enabled": False},
        },
    }

    if config:
        print(f"Updating existing portal config {config.id}...")
        stripe.billing_portal.Configuration.modify(config.id, **params)
        print(f"OK: Customer Portal configured. Return URL: {return_url}")
    else:
        print("Creating new portal config...")
        stripe.billing_portal.Configuration.create(**params)
        print(f"OK: Customer Portal configured. Return URL: {return_url}")

    print("Customers can now manage subscriptions, update payment method, and cancel.")


if __name__ == "__main__":
    main()
