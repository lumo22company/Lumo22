#!/usr/bin/env python3
"""
Create Stripe recurring price for 30 Days Captions at £79/month.
Uses existing 30 Days Captions product if STRIPE_CAPTIONS_PRICE_ID is set; otherwise creates a product.
Run from project root: python3 scripts/create_captions_subscription_price.py
Prints STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID=price_xxx for .env and Railway.
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
    product_id = None
    if one_off_price_id:
        try:
            price = stripe.Price.retrieve(one_off_price_id)
            product_id = price.product if hasattr(price, "product") else price.get("product")
        except Exception as e:
            print(f"Could not retrieve product from price {one_off_price_id}: {e}")

    if not product_id:
        prod = stripe.Product.create(
            name="30 Days of Social Media Captions",
            description="30 days of captions, written for your brand. Subscription: new pack each month.",
        )
        product_id = prod.id
        print(f"Created product: {product_id}")

    price = stripe.Price.create(
        product=product_id,
        unit_amount=7900,
        currency="gbp",
        recurring={"interval": "month"},
    )
    print(f"STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID={price.id}")
    return price.id

if __name__ == "__main__":
    main()
