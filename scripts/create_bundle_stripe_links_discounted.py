#!/usr/bin/env python3
"""
Create Stripe bundle products (email + chat) at discounted totals:
  (tier + £59) with 5% off → £131, £198, £340/month.

Requires: .env with STRIPE_SECRET_KEY and BASE_URL.
Run from project root: python3 scripts/create_bundle_stripe_links_discounted.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

BUNDLE_DISCOUNT_PERCENT = 5
CHAT_PRICE = 59
TIERS = [
    ("Starter", 79, "ACTIVATION_LINK_STARTER_BUNDLE"),
    ("Standard", 149, "ACTIVATION_LINK_STANDARD_BUNDLE"),
    ("Premium", 299, "ACTIVATION_LINK_PREMIUM_BUNDLE"),
]

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip().rstrip("/")
    if not secret or not base_url.startswith("http"):
        print("ERROR: STRIPE_SECRET_KEY and BASE_URL required in .env")
        sys.exit(1)

    stripe.api_key = secret
    bundle_success = f"{base_url}/activate-success"

    print(f"Creating bundle products (tier + £{CHAT_PRICE}, {BUNDLE_DISCOUNT_PERCENT}% off)...")
    print(f"Success URL: {bundle_success}\n")

    for name, tier_price, env_name in TIERS:
        total_before = tier_price + CHAT_PRICE
        discounted = round(total_before * (1 - BUNDLE_DISCOUNT_PERCENT / 100))
        pence = discounted * 100
        prod = stripe.Product.create(
            name=f"Email {name} + Chat",
            description=f"Digital Front Desk {name} + Chat Assistant — £{discounted}/month ({BUNDLE_DISCOUNT_PERCENT}% off bundle).",
        )
        price = stripe.Price.create(
            product=prod.id,
            unit_amount=pence,
            currency="gbp",
            recurring={"interval": "month"},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={"type": "redirect", "redirect": {"url": bundle_success}},
        )
        print(f"  {name} + chat: £{discounted}/month → {env_name}")
        print(f"    {link.url}")

    print("\nAdd the new bundle URLs to .env (ACTIVATION_LINK_*_BUNDLE) and run webhook update for amounts:", [f"£{round((t[1] + CHAT_PRICE) * (1 - BUNDLE_DISCOUNT_PERCENT/100))}" for t in TIERS])

if __name__ == "__main__":
    main()
