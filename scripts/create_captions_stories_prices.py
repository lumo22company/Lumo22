#!/usr/bin/env python3
"""
Create Stripe product and prices for 30 Days Story Ideas add-on:
- One-off £19 (STRIPE_CAPTIONS_STORIES_PRICE_ID)
- Subscription £12/month (STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID)

Run from project root: python3 scripts/create_captions_stories_prices.py
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

    product = stripe.Product.create(
        name="30 Days Story Ideas",
        description="30 one-line Story prompts for Instagram & Facebook each month. Add-on for 30 Days Captions.",
    )
    print(f"Created product: {product.name} ({product.id})")

    price_oneoff = stripe.Price.create(
        product=product.id,
        unit_amount=1900,
        currency="gbp",
    )
    print(f"\nSTRIPE_CAPTIONS_STORIES_PRICE_ID={price_oneoff.id}")

    price_sub = stripe.Price.create(
        product=product.id,
        unit_amount=1200,
        currency="gbp",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID={price_sub.id}")

    print("\nAdd the above lines to .env and Railway.")
    print("Run: python3 run_caption_orders_stories_migration.py (or run database_caption_orders_stories.sql in Supabase)")


if __name__ == "__main__":
    main()
