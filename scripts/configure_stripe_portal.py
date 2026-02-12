#!/usr/bin/env python3
"""
Configure Stripe Customer Portal: enable subscription management, cancel, payment method update.
Run from project root: python3 scripts/configure_stripe_portal.py
Requires: .env with STRIPE_SECRET_KEY, BASE_URL
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
            "invoice_history": {"enabled": True},
            "payment_method_update": {"enabled": True},
            "subscription_cancel": {
                "enabled": True,
                "mode": "at_period_end",
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
