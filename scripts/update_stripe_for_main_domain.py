#!/usr/bin/env python3
"""
Update all Stripe Payment Links and webhook to use your main domain (BASE_URL).

Run: python3 scripts/update_stripe_for_main_domain.py

Requires: .env with STRIPE_SECRET_KEY and BASE_URL (e.g. https://www.lumo22.com)

What it does:
- Updates each Payment Link's success redirect to BASE_URL + correct path
- Updates Stripe webhook endpoint URL to BASE_URL/webhooks/stripe
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

# Mapping: env var name -> (success path, description)
# Note: Chat/DFD/Bundle links removed — Captions is the only active product.
PAYMENT_LINK_CONFIG = {
    "CAPTIONS_PAYMENT_LINK": ("/captions-thank-you", "Captions one-off"),
}


def main():
    secret = os.getenv("STRIPE_SECRET_KEY", "").strip()
    base = (os.getenv("BASE_URL") or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://www.lumo22.com"
        print(f"BASE_URL not set or invalid; using {base}")
    else:
        print(f"Using BASE_URL: {base}")

    if not secret:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)

    import stripe
    stripe.api_key = secret

    # Collect payment link URLs from env
    env_urls = {}
    for var, (path, _) in PAYMENT_LINK_CONFIG.items():
        url = (os.getenv(var) or "").strip()
        if url and url.startswith("https://buy.stripe.com"):
            env_urls[url] = (path, PAYMENT_LINK_CONFIG[var][1])

    if not env_urls:
        print("No Payment Link URLs found in env (CAPTIONS_PAYMENT_LINK)")
    else:
        print(f"\nFound {len(env_urls)} Payment Link(s) in env")

    # List all payment links from Stripe
    try:
        links = stripe.PaymentLink.list(limit=100)
        stripe_url_to_id = {pl["url"]: pl["id"] for pl in links.get("data", [])}
    except stripe.error.StripeError as e:
        print(f"ERROR listing Payment Links: {e}")
        stripe_url_to_id = {}

    updated_links = 0
    for env_url, (path, desc) in env_urls.items():
        plink_id = stripe_url_to_id.get(env_url)
        if not plink_id:
            print(f"  Skip (not in Stripe): {desc}")
            continue
        new_redirect = f"{base}{path}"
        try:
            stripe.PaymentLink.modify(
                plink_id,
                after_completion={"type": "redirect", "redirect": {"url": new_redirect}},
            )
            print(f"  OK: {desc} -> {new_redirect}")
            updated_links += 1
        except stripe.error.StripeError as e:
            print(f"  ERROR {desc}: {e}")

    # Update webhook
    print("\nWebhook endpoint:")
    try:
        endpoints = stripe.WebhookEndpoint.list(limit=20)
        for ep in endpoints.get("data", []):
            url = ep.get("url", "")
            if "/webhooks/stripe" in url or "stripe" in url.lower():
                new_url = f"{base}/webhooks/stripe"
                if url.strip().rstrip("/") == new_url.strip().rstrip("/"):
                    print(f"  OK: Already {new_url}")
                else:
                    stripe.WebhookEndpoint.modify(ep["id"], url=new_url)
                    print(f"  OK: Updated to {new_url}")
                    break
        else:
            print("  No webhook endpoint with /webhooks/stripe found. Add one in Stripe Dashboard.")
    except stripe.error.StripeError as e:
        print(f"  ERROR: {e}")

    print(f"\nDone. Updated {updated_links} Payment Link(s).")
    print("Ensure BASE_URL is set to your main domain in Railway (e.g. https://www.lumo22.com).")


if __name__ == "__main__":
    main()
