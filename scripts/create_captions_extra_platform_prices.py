#!/usr/bin/env python3
"""
Create Stripe prices for 30 Days Captions extra platform add-on:
- One-off £29 (STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID)
- Subscription £19/month (STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID)
Uses the same product as the base Captions price (from STRIPE_CAPTIONS_PRICE_ID).
Run from project root: python3 scripts/create_captions_extra_platform_prices.py
Prints env vars for .env and Railway.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)

    stripe.api_key = secret
    one_off_price_id = (os.getenv("STRIPE_CAPTIONS_PRICE_ID") or "").strip()
    if not one_off_price_id:
        print("ERROR: STRIPE_CAPTIONS_PRICE_ID not set. Create base Captions product first.")
        sys.exit(1)

    try:
        price = stripe.Price.retrieve(one_off_price_id)
        product_id = price.product if hasattr(price, "product") else price.get("product")
    except Exception as e:
        print(f"Could not retrieve product from STRIPE_CAPTIONS_PRICE_ID: {e}")
        sys.exit(1)

    # One-off £29 per extra platform
    price_oneoff = stripe.Price.create(
        product=product_id,
        unit_amount=2900,
        currency="gbp",
    )
    print(f"STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID={price_oneoff.id}")

    # Recurring £19/month per extra platform
    price_sub = stripe.Price.create(
        product=product_id,
        unit_amount=1900,
        currency="gbp",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID={price_sub.id}")
    print("\nAdd the above lines to .env and Railway. Run database_caption_orders_platforms.sql in Supabase if not already done.")

if __name__ == "__main__":
    main()
