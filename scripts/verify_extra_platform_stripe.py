#!/usr/bin/env python3
"""Verify Extra platform Stripe product and prices are configured correctly."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

EXPECTED_DESCRIPTION = "Extra platform for your 30 Days Captions pack. Content delivered with your next pack."

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    price_id = os.getenv("STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID", "").strip()
    sub_price_id = os.getenv("STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", "").strip()

    if not secret:
        print("FAIL: STRIPE_SECRET_KEY not set")
        return 1
    if not price_id or not sub_price_id:
        print("FAIL: STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID or SUBSCRIPTION_PRICE_ID not set in .env")
        return 1

    stripe.api_key = secret
    errors = []

    for label, pid in [("One-off", price_id), ("Subscription", sub_price_id)]:
        try:
            price = stripe.Price.retrieve(pid, expand=["product"])
            product = price.get("product") if isinstance(price.get("product"), dict) else stripe.Product.retrieve(price["product"])
            name = product.get("name") or ""
            desc = (product.get("description") or "").strip()
            if name != "Extra platform":
                errors.append(f"{label} price {pid}: product name is '{name}', expected 'Extra platform'")
            elif desc != EXPECTED_DESCRIPTION:
                errors.append(f"{label} price {pid}: product description mismatch (got {len(desc)} chars)")
            else:
                print(f"OK {label}: {pid} -> product '{name}', description OK")
        except stripe.error.InvalidRequestError as e:
            errors.append(f"{label} price {pid}: {e}")
        except Exception as e:
            errors.append(f"{label} price {pid}: {e}")

    if errors:
        for e in errors:
            print("FAIL:", e)
        return 1
    print("\nExtra platform setup OK. Checkout will show 'Extra platform' with correct description.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
