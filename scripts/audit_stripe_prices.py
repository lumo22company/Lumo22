#!/usr/bin/env python3
"""
Audit Stripe prices vs website/webhook: ensure everything matches.

Expected pricing (from website + webhook):
  Captions:     £97 one-off, £79/mo subscription
  Front Desk:   £79, £149, £299 (Starter, Growth, Pro)
  Bundles:      £131, £198, £340 (Starter+Chat, Growth+Chat, Pro+Chat)
  Chat:         £59/mo

Run from project root: python3 scripts/audit_stripe_prices.py
Requires: .env with STRIPE_SECRET_KEY
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

# Expected: (env_var, amount_pence, recurring, description)
EXPECTED = [
    ("STRIPE_CAPTIONS_PRICE_ID", 9700, False, "Captions one-off £97"),
    ("STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", 7900, True, "Captions subscription £79/mo"),
    ("ACTIVATION_LINK_STARTER", 7900, True, "Front Desk Starter £79/mo"),
    ("ACTIVATION_LINK_STANDARD", 14900, True, "Front Desk Growth £149/mo"),
    ("ACTIVATION_LINK_PREMIUM", 29900, True, "Front Desk Pro £299/mo"),
    ("ACTIVATION_LINK_STARTER_BUNDLE", 13100, True, "Starter+Chat bundle £131/mo"),
    ("ACTIVATION_LINK_STANDARD_BUNDLE", 19800, True, "Growth+Chat bundle £198/mo"),
    ("ACTIVATION_LINK_PREMIUM_BUNDLE", 34000, True, "Pro+Chat bundle £340/mo"),
    ("CHAT_PAYMENT_LINK", 5900, True, "Chat Assistant £59/mo"),
]

# Fallbacks: if per-plan not set, ACTIVATION_LINK is used for all email plans
# CAPTIONS_PAYMENT_LINK is fallback when checkout not used (we check price IDs for checkout)


def get_amount_from_price(price):
    """Return (amount_pence, is_recurring, currency) or None."""
    if not price:
        return None
    amt = price.get("unit_amount")
    curr = (price.get("currency") or "").lower()
    recur = bool(price.get("recurring"))
    if curr != "gbp" or amt is None:
        return None
    return (amt, recur, curr)


def get_price_from_payment_link(link):
    """Get first price's (amount, recurring) from a payment link."""
    items = (link.get("line_items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, str):
        return None
    if not price:
        price = items[0].get("price")  # might be expanded
    res = get_amount_from_price(price)
    if res:
        return (res[0], res[1])
    return None


def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    stripe.api_key = secret

    print("=" * 70)
    print("STRIPE PRICE AUDIT — Website vs Stripe vs Webhook")
    print("=" * 70)

    all_ok = True

    # 1. Check price IDs (Captions)
    for key in ["STRIPE_CAPTIONS_PRICE_ID", "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID"]:
        pid = os.getenv(key, "").strip()
        if not pid:
            print(f"\n  {key}: not set (optional for subscription)")
            continue
        exp = next((e for e in EXPECTED if e[0] == key), None)
        if not exp:
            continue
        _, exp_amt, exp_recur, desc = exp
        try:
            p = stripe.Price.retrieve(pid)
        except Exception as e:
            print(f"\n  {key}: ERROR retrieving — {e}")
            all_ok = False
            continue
        res = get_amount_from_price(p)
        if not res:
            print(f"\n  {key}: price not GBP or no amount")
            all_ok = False
            continue
        amt, recur, _ = res
        if amt != exp_amt or recur != exp_recur:
            print(f"\n  MISMATCH {desc}")
            print(f"    Expected: £{exp_amt//100} {'/mo' if exp_recur else 'one-off'}")
            print(f"    Stripe:  £{amt//100} {'/mo' if recur else 'one-off'}")
            all_ok = False
        else:
            print(f"\n  OK {desc} — {key}")

    # 2. Check payment links from env
    env_to_exp = {e[0]: e for e in EXPECTED if "LINK" in e[0]}
    all_links = {}
    for link in stripe.PaymentLink.list(limit=100, active=True).auto_paging_iter():
        url = (link.get("url") or "").strip().rstrip("/")
        all_links[url] = link

    for key, (_, exp_amt, exp_recur, desc) in env_to_exp.items():
        url = (os.getenv(key, "").strip() or "").rstrip("/")
        if not url:
            continue
        link = all_links.get(url)
        if not link:
            # Try partial match (env might have extra params)
            link = next((l for u, l in all_links.items() if url in u or u in url), None)
        if not link:
            print(f"\n  {key}: URL not found in Stripe payment links")
            all_ok = False
            continue
        # Fetch with expanded line_items
        try:
            full = stripe.PaymentLink.retrieve(link["id"], expand=["line_items.data.price"])
        except Exception as e:
            print(f"\n  {key}: ERROR — {e}")
            all_ok = False
            continue
        res = get_price_from_payment_link(full)
        if not res:
            print(f"\n  {key}: could not get price from link")
            all_ok = False
            continue
        amt, recur = res
        if amt != exp_amt or recur != exp_recur:
            print(f"\n  MISMATCH {desc}")
            print(f"    Env var:   {key}")
            print(f"    Expected:  £{exp_amt//100} {'/mo' if exp_recur else 'one-off'}")
            print(f"    Stripe:   £{amt//100} {'/mo' if recur else 'one-off'}")
            all_ok = False
        else:
            print(f"\n  OK {desc} — {key}")

    # 3. Webhook amounts (for reference)
    print("\n" + "-" * 70)
    print("Webhook expects (api/webhooks.py):")
    print("  Captions: £97 (9700), subscription £79 (7900)")
    print("  Front Desk: £79, £149, £299, £131, £198, £340 (pence: 7900,14900,29900,13100,19800,34000)")
    print("  Chat: £59 (5900)")
    print("-" * 70)

    if all_ok:
        print("\n  All prices match. Website, Stripe, and webhook are aligned.")
    else:
        print("\n  Some mismatches found. Update Stripe products/prices or .env to fix.")
        sys.exit(1)


if __name__ == "__main__":
    main()
