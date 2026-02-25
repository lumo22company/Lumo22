#!/usr/bin/env python3
"""
Create Stripe Prices for 30 Days Captions in USD and EUR (so the currency selector works).

Uses your existing GBP price IDs from env to find the products, then creates:
- One-off: USD $119, EUR €109
- Subscription: USD $99/month, EUR €89/month

Run from project root: python3 scripts/create_captions_usd_eur_prices.py
Then add the printed env vars to .env and Railway.
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

    oneoff_gbp_id = os.getenv("STRIPE_CAPTIONS_PRICE_ID", "").strip()
    sub_gbp_id = os.getenv("STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", "").strip()
    if not oneoff_gbp_id or not sub_gbp_id:
        print("ERROR: Set STRIPE_CAPTIONS_PRICE_ID and STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID in .env first.")
        sys.exit(1)

    # Get product IDs from existing GBP prices
    oneoff_price = stripe.Price.retrieve(oneoff_gbp_id)
    sub_price = stripe.Price.retrieve(sub_gbp_id)
    product_oneoff = oneoff_price["product"] if isinstance(oneoff_price["product"], str) else oneoff_price["product"]["id"]
    product_sub = sub_price["product"] if isinstance(sub_price["product"], str) else sub_price["product"]["id"]

    print("Creating USD and EUR prices for 30 Days Captions...\n")

    # One-off: USD $119, EUR €109
    price_oneoff_usd = stripe.Price.create(
        product=product_oneoff,
        unit_amount=11900,  # $119.00
        currency="usd",
    )
    print(f"STRIPE_CAPTIONS_PRICE_ID_USD={price_oneoff_usd.id}")

    price_oneoff_eur = stripe.Price.create(
        product=product_oneoff,
        unit_amount=10900,  # €109.00
        currency="eur",
    )
    print(f"STRIPE_CAPTIONS_PRICE_ID_EUR={price_oneoff_eur.id}")

    # Subscription: USD $99/mo, EUR €89/mo
    price_sub_usd = stripe.Price.create(
        product=product_sub,
        unit_amount=9900,
        currency="usd",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD={price_sub_usd.id}")

    price_sub_eur = stripe.Price.create(
        product=product_sub,
        unit_amount=8900,
        currency="eur",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR={price_sub_eur.id}")

    print("\nAdd the above four lines to .env and Railway, then redeploy. The currency selector will appear on /captions.")


if __name__ == "__main__":
    main()
