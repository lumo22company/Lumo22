#!/usr/bin/env python3
"""
Create a dedicated Stripe Product for the extra-platform add-on so checkout shows
"Extra platform" (or similar) instead of the base product name.

Creates:
- Product: "Extra platform" with clear description
- One-off £29 price (STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID)
- Subscription £19/month price (STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID)

Run from project root: python3 scripts/create_extra_platform_product_prices.py

Then update .env and Railway with the printed price IDs. You can archive the old
extra platform prices (the ones that showed "30 Days of Social Media Captions") in
Stripe Dashboard → Products → [old product] → archive the £29 and £19 prices, or
leave them and just switch env to the new IDs.
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

    product = stripe.Product.create(
        name="Extra platform",
        description="Extra platform for your 30 Days Captions pack. Content delivered with your next pack.",
    )
    print(f"Created product: {product.id} — Extra platform")

    price_oneoff = stripe.Price.create(
        product=product.id,
        unit_amount=2900,
        currency="gbp",
    )
    print(f"\nSTRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID={price_oneoff.id}")

    price_sub = stripe.Price.create(
        product=product.id,
        unit_amount=1900,
        currency="gbp",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID={price_sub.id}")

    print("\nAdd or update these in .env and Railway. In Stripe Checkout the add-on will now show as 'Extra platform'.")

if __name__ == "__main__":
    main()
