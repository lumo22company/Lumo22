#!/usr/bin/env python3
"""
Audit Stripe products: which are IN USE vs safe to archive.

Compares your Stripe Dashboard products/prices against what this app actually uses.
Run from project root: python3 scripts/audit_stripe_products.py

Add --archive to actually archive the unused products (otherwise just reports).
Requires: .env with STRIPE_SECRET_KEY
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

# --- What the app uses (from config and webhooks) ---
CAPTIONS_AMOUNT_PENCE = 9700   # £97 one-off
CAPTIONS_SUB_AMOUNT_PENCE = 7900  # £79/month subscription
FRONT_DESK_AMOUNTS_PENCE = {7900, 14900, 29900, 13100, 19800, 34000}
CHAT_AMOUNTS_PENCE = {5900}

# All amounts the webhook recognises
KEEP_AMOUNTS_PENCE = FRONT_DESK_AMOUNTS_PENCE | CHAT_AMOUNTS_PENCE | {CAPTIONS_AMOUNT_PENCE, CAPTIONS_SUB_AMOUNT_PENCE}

# Price IDs from env (these are definitely in use)
def get_env_price_ids():
    ids = set()
    for key in ["STRIPE_CAPTIONS_PRICE_ID", "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID"]:
        v = os.getenv(key, "").strip()
        if v:
            ids.add(v)
    return ids

# Payment link URLs from env (we'll fetch links and match)
def get_env_payment_link_urls():
    keys = [
        "CAPTIONS_PAYMENT_LINK",
        "CHAT_PAYMENT_LINK",
        "ACTIVATION_LINK",
        "ACTIVATION_LINK_STARTER", "ACTIVATION_LINK_STANDARD", "ACTIVATION_LINK_PREMIUM",
        "ACTIVATION_LINK_STARTER_BUNDLE", "ACTIVATION_LINK_STANDARD_BUNDLE", "ACTIVATION_LINK_PREMIUM_BUNDLE",
        "CHAT_PAYMENT_LINK_STARTER", "CHAT_PAYMENT_LINK_GROWTH", "CHAT_PAYMENT_LINK_PRO",
    ]
    urls = set()
    for k in keys:
        v = os.getenv(k, "").strip()
        if v:
            urls.add(v.rstrip("/"))
    return urls


def main():
    parser = argparse.ArgumentParser(description="Audit Stripe products")
    parser.add_argument("--archive", action="store_true", help="Archive unused products (default: report only)")
    args = parser.parse_args()

    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    stripe.api_key = secret

    env_price_ids = get_env_price_ids()
    env_link_urls = get_env_payment_link_urls()

    # Collect payment link IDs that are in .env
    in_use_link_ids = set()
    if env_link_urls:
        for pl in stripe.PaymentLink.list(limit=100).auto_paging_iter():
            url = (pl.get("url") or "").rstrip("/")
            if url in env_link_urls or any(u in url for u in env_link_urls):
                in_use_link_ids.add(pl["id"])

    # Get prices used by in-use payment links
    in_use_price_ids = set(env_price_ids)
    for plid in in_use_link_ids:
        try:
            pl = stripe.PaymentLink.retrieve(plid, expand=["line_items.data.price"])
            for item in (pl.get("line_items") or {}).get("data") or []:
                price = item.get("price")
                if price:
                    pid = price.get("id") if isinstance(price, dict) else getattr(price, "id", None)
                    if pid:
                        in_use_price_ids.add(pid)
        except Exception as e:
            print(f"  Warning: could not expand link {plid}: {e}")

    # Fetch all products and their prices
    print("Fetching products and prices from Stripe...")
    print()
    in_use_products = []
    unused_products = []

    for product in stripe.Product.list(limit=100, expand=["data.default_price"]).auto_paging_iter():
        if product.get("deleted"):
            continue
        name = product.get("name") or "(unnamed)"
        prod_id = product.get("id")

        # Get all prices for this product
        prices = list(stripe.Price.list(product=prod_id, limit=100).auto_paging_iter())
        if not prices:
            # Product with no prices — usually safe to archive
            unused_products.append((product, [], "no prices"))
            continue

        used_reasons = []
        any_used = False
        for p in prices:
            if p.get("deleted"):
                continue
            pid = p.get("id")
            if pid in in_use_price_ids:
                used_reasons.append(f"price {pid[:20]}... in env or in-use payment link")
                any_used = True
            else:
                amount = p.get("unit_amount")
                recur = p.get("recurring")
                curr = (p.get("currency") or "").lower()
                if curr == "gbp" and amount is not None:
                    if recur:
                        if amount in KEEP_AMOUNTS_PENCE:
                            used_reasons.append(f"price £{amount//100}/mo matches webhook")
                            any_used = True
                    else:
                        if amount == CAPTIONS_AMOUNT_PENCE:
                            used_reasons.append(f"price £{amount//100} one-off matches captions")
                            any_used = True

        if any_used:
            in_use_products.append((product, prices, used_reasons))
        else:
            unused_products.append((product, prices, "no matching env vars or webhook amounts"))

    # Report
    print("=" * 60)
    print("STRIPE PRODUCTS IN USE (keep these)")
    print("=" * 60)
    for prod, prices, reasons in in_use_products:
        print(f"\n  {prod.get('name')} (prod_{prod.get('id')})")
        for r in reasons:
            print(f"    -> {r}")

    print("\n")
    print("=" * 60)
    print("STRIPE PRODUCTS NOT USED (safe to archive)")
    print("=" * 60)
    if not unused_products:
        print("\n  None found. All products appear to be in use.")
    else:
        for prod, prices, reason in unused_products:
            name = prod.get("name") or "(unnamed)"
            print(f"\n  {name} (prod_{prod.get('id')})")
            print(f"    Reason: {reason}")
            for p in prices[:3]:
                if p.get("deleted"):
                    continue
                amt = p.get("unit_amount")
                curr = (p.get("currency") or "").upper()
                recur = " recurring" if p.get("recurring") else ""
                print(f"    - Price {p.get('id')}: {curr} {amt/100 if amt else '?'}{recur}")
            if len(prices) > 3:
                print(f"    ... and {len(prices)-3} more price(s)")

    if args.archive and unused_products:
        print("\n")
        print("=" * 60)
        print("ARCHIVING UNUSED PRODUCTS")
        print("=" * 60)
        for prod, _, _ in unused_products:
            pid = prod.get("id")
            name = prod.get("name") or "(unnamed)"
            try:
                stripe.Product.modify(pid, active=False)
                print(f"  Archived: {name} ({pid})")
            except Exception as e:
                print(f"  ERROR archiving {name}: {e}")
        print("Done.")
    elif not args.archive:
        print("\n")
        print("=" * 60)
        print("HOW TO ARCHIVE")
        print("=" * 60)
        print("Run with --archive to archive unused products:")
        print("  python3 scripts/audit_stripe_products.py --archive")
        print()
        print("Or manually: Stripe Dashboard → Products → ⋮ → Archive product")
        print()


if __name__ == "__main__":
    main()
