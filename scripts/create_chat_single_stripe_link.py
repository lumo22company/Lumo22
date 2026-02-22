#!/usr/bin/env python3
"""
Create one Stripe product and payment link for Chat Assistant at £59/month.
Requires: .env with STRIPE_SECRET_KEY and BASE_URL (no trailing slash).
Run from project root: python3 scripts/create_chat_single_stripe_link.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip().rstrip("/")
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    if not base_url or not base_url.startswith("http"):
        print("ERROR: BASE_URL must be set in .env")
        sys.exit(1)

    stripe.api_key = secret
    chat_success = f"{base_url}/website-chat-success"

    print("Creating Chat Assistant product (£59/month) and payment link...")
    print(f"Success URL: {chat_success}\n")

    prod = stripe.Product.create(
        name="Chat Assistant",
        description="Chat on your website — £59/month. Answers FAQs, captures leads, encourages bookings.",
    )
    price = stripe.Price.create(
        product=prod.id,
        unit_amount=5900,  # £59
        currency="gbp",
        recurring={"interval": "month"},
    )
    link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        after_completion={"type": "redirect", "redirect": {"url": chat_success}},
        metadata={"product": "chat"},
    )

    print(f"CHAT_PAYMENT_LINK={link.url}")
    return link.url

if __name__ == "__main__":
    main()
