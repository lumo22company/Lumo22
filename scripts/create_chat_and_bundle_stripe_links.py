#!/usr/bin/env python3
"""
Create Stripe products, prices, and payment links for:
- Chat Assistant standalone: Starter £59, Growth £99, Pro £149/month
- Email + Chat bundle: £104, £184, £344/month

Requires: .env with STRIPE_SECRET_KEY and BASE_URL (no trailing slash).
Run from project root: python3 scripts/create_chat_and_bundle_stripe_links.py
"""
import os
import sys

# Load .env from project root
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
        print("ERROR: BASE_URL must be set in .env (e.g. https://your-app.up.railway.app)")
        sys.exit(1)

    stripe.api_key = secret
    chat_success = f"{base_url}/website-chat-success"
    bundle_success = f"{base_url}/activate-success"

    print("Creating Stripe products, prices, and payment links...")
    print(f"Chat success URL: {chat_success}")
    print(f"Bundle success URL: {bundle_success}\n")

    # --- Chat Assistant standalone: £59, £99, £149 ---
    chat_tiers = [
        ("Chat Assistant — Starter", 59, "CHAT_PAYMENT_LINK_STARTER"),
        ("Chat Assistant — Growth", 99, "CHAT_PAYMENT_LINK_GROWTH"),
        ("Chat Assistant — Pro", 149, "CHAT_PAYMENT_LINK_PRO"),
    ]
    chat_links = {}
    for name, pounds, env_name in chat_tiers:
        prod = stripe.Product.create(name=name, description=f"Chat Assistant on your website — £{pounds}/month")
        price = stripe.Price.create(
            product=prod.id,
            unit_amount=pounds * 100,  # pence
            currency="gbp",
            recurring={"interval": "month"},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={"type": "redirect", "redirect": {"url": chat_success}},
            metadata={"product": "chat"},
        )
        chat_links[env_name] = link.url
        print(f"  {name}: {link.url}")

    # First chat link as fallback for CHAT_PAYMENT_LINK
    first_chat_url = chat_links["CHAT_PAYMENT_LINK_STARTER"]

    # --- Email + Chat bundle: £104, £184, £344 ---
    bundle_tiers = [
        ("Email Starter + Chat", 104, "ACTIVATION_LINK_STARTER_BUNDLE"),
        ("Email Standard + Chat", 184, "ACTIVATION_LINK_STANDARD_BUNDLE"),
        ("Email Premium + Chat", 344, "ACTIVATION_LINK_PREMIUM_BUNDLE"),
    ]
    bundle_links = {}
    for name, pounds, env_name in bundle_tiers:
        prod = stripe.Product.create(name=name, description=f"Digital Front Desk + Chat Assistant — £{pounds}/month")
        price = stripe.Price.create(
            product=prod.id,
            unit_amount=pounds * 100,
            currency="gbp",
            recurring={"interval": "month"},
        )
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={"type": "redirect", "redirect": {"url": bundle_success}},
        )
        bundle_links[env_name] = link.url
        print(f"  {name}: {link.url}")

    print("\n--- Add these to your .env and Railway Variables ---\n")
    print(f"CHAT_PAYMENT_LINK={first_chat_url}")
    for k, v in chat_links.items():
        print(f"{k}={v}")
    for k, v in bundle_links.items():
        print(f"{k}={v}")
    print("\nDone.")

if __name__ == "__main__":
    main()
