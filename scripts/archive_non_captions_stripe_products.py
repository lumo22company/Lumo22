#!/usr/bin/env python3
"""
Archive all Stripe products except 30 Days Captions and 30 Days Story Ideas.
Run from project root: python3 scripts/archive_non_captions_stripe_products.py
Requires: .env with STRIPE_SECRET_KEY
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

# Product names we KEEP (captions + stories only)
KEEP_NAMES = {
    "30 Days of Social Media Captions",
    "30 Days Story Ideas",
}


def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    stripe.api_key = secret

    print("Fetching products from Stripe...")
    to_archive = []
    kept = []

    for product in stripe.Product.list(limit=100).auto_paging_iter():
        if product.get("deleted"):
            continue
        name = product.get("name") or "(unnamed)"
        pid = product.get("id")
        if name in KEEP_NAMES:
            kept.append((pid, name))
        else:
            to_archive.append((pid, name))

    print("\nKeeping (do not archive):")
    for pid, name in kept:
        print(f"  {name} ({pid})")

    print("\nArchiving:")
    for pid, name in to_archive:
        print(f"  {name} ({pid})")
        try:
            stripe.Product.modify(pid, active=False)
            print(f"    -> archived")
        except stripe.error.StripeError as e:
            print(f"    -> ERROR: {e}")

    print(f"\nDone. Kept {len(kept)} product(s), archived {len(to_archive)} product(s).")


if __name__ == "__main__":
    main()
