#!/usr/bin/env python3
"""
Create new Stripe prices for the 30 Days Story Ideas add-on:
- One-off £29 (STRIPE_CAPTIONS_STORIES_PRICE_ID)
- Subscription £17/month (STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID)

Finds the existing "30 Days Story Ideas" product (from your current Stories price ID or by name)
and creates the new prices on it. After running, update .env and Railway with the printed IDs.
You can archive the old £19 / £12 prices in Stripe Dashboard if you like.

Run from project root: python3 scripts/update_stories_addon_prices.py
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
    product_id = None

    # Try to get product from existing Stories price ID
    existing_price_id = os.getenv("STRIPE_CAPTIONS_STORIES_PRICE_ID", "").strip()
    if existing_price_id:
        try:
            price = stripe.Price.retrieve(existing_price_id)
            product_id = price.product if isinstance(price.product, str) else (price.product.id if hasattr(price.product, "id") else None)
            if product_id:
                print(f"Using product from existing price: {product_id}")
        except stripe.error.StripeError as e:
            print(f"Could not retrieve existing price: {e}")

    if not product_id:
        for p in stripe.Product.list(limit=100).auto_paging_iter():
            if "30 Days Story Ideas" in (p.name or ""):
                product_id = p.id
                print(f"Found product by name: {product_id}")
                break

    if not product_id:
        print("ERROR: Could not find '30 Days Story Ideas' product. Create it first with scripts/create_captions_stories_prices.py (then run this script to add the new prices).")
        sys.exit(1)

    price_oneoff = stripe.Price.create(
        product=product_id,
        unit_amount=2900,
        currency="gbp",
    )
    print(f"\nSTRIPE_CAPTIONS_STORIES_PRICE_ID={price_oneoff.id}")

    price_sub = stripe.Price.create(
        product=product_id,
        unit_amount=1700,
        currency="gbp",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID={price_sub.id}")

    print("\nUpdate .env and Railway with the two lines above, then redeploy.")
    print("Optional: in Stripe Dashboard → Products → 30 Days Story Ideas, archive the old £19 / £12 prices.")


if __name__ == "__main__":
    main()
