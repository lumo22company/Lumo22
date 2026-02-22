#!/usr/bin/env python3
"""
Keep only the correct payment links in Stripe; archive the rest.

Correct links (one each): £59 (chat), £79, £149, £299 (email), £131, £198, £340 (bundles).
Prefers links whose URL is in .env (CHAT_PAYMENT_LINK, ACTIVATION_LINK_*, etc.).
All others are archived (active=False).

Requires: .env with STRIPE_SECRET_KEY.
Run from project root: python3 scripts/cleanup_stripe_payment_links.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import stripe

# One payment link per amount (pence, GBP monthly). All others will be archived.
KEEP_AMOUNTS_PENCE = {
    5900,   # Chat Assistant £59
    7900,   # Starter email £79
    14900,  # Standard email £149
    29900,  # Premium email £299
    13100,  # Starter + chat £131
    19800,  # Standard + chat £198
    34000,  # Premium + chat £340
}

def get_preferred_urls():
    """URLs from .env that we want to keep (strip and normalise)."""
    keys = [
        "CHAT_PAYMENT_LINK",
        "ACTIVATION_LINK", "ACTIVATION_LINK_STARTER", "ACTIVATION_LINK_STANDARD", "ACTIVATION_LINK_PREMIUM",
        "ACTIVATION_LINK_STARTER_BUNDLE", "ACTIVATION_LINK_STANDARD_BUNDLE", "ACTIVATION_LINK_PREMIUM_BUNDLE",
    ]
    urls = set()
    for k in keys:
        v = os.getenv(k, "").strip()
        if v:
            urls.add(v.rstrip("/"))
    return urls

def get_link_amount(link):
    """Get recurring unit_amount in pence for this payment link, or None."""
    items = link.get("line_items") or {}
    data = items.get("data") or []
    if not data:
        return None
    first = data[0]
    price = first.get("price") if isinstance(first.get("price"), dict) else None
    if not price:
        return None
    if price.get("recurring") and price.get("currency") == "gbp":
        return price.get("unit_amount")
    return None

def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)
    stripe.api_key = secret

    print("Fetching all payment links...")
    links = []
    for link in stripe.PaymentLink.list(limit=100).auto_paging_iter():
        # Retrieve with line_items expanded to get price amount
        full = stripe.PaymentLink.retrieve(link["id"], expand=["line_items.data.price"])
        links.append(full)

    print(f"Found {len(links)} payment link(s).")
    by_amount = {}
    for link in links:
        amount = get_link_amount(link)
        if amount is None:
            print(f"  Skip (no recurring GBP price): {link['id']}")
            continue
        by_amount.setdefault(amount, []).append(link)

    preferred = get_preferred_urls()
    to_archive = []
    for amount, group in by_amount.items():
        label = f"£{amount // 100}"
        if amount in KEEP_AMOUNTS_PENCE:
            # Prefer link whose url is in .env; else keep newest
            group.sort(key=lambda x: (
                0 if (x.get("url") or "").rstrip("/") in preferred else 1,
                -x.get("created", 0),
            ))
            for i, link in enumerate(group):
                if i == 0:
                    print(f"  KEEP {label}: {link['id']} (url: {link.get('url', '')[:50]}...)")
                else:
                    to_archive.append((link, f"duplicate {label}"))
        else:
            for link in group:
                to_archive.append((link, f"obsolete {label}"))

    if not to_archive:
        print("Nothing to archive.")
        return

    print(f"\nArchive {len(to_archive)} link(s):")
    for link, reason in to_archive:
        print(f"  {reason}: {link['id']}")
        try:
            stripe.PaymentLink.modify(link["id"], active=False)
            print(f"    -> archived")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    print("Done.")

if __name__ == "__main__":
    main()
