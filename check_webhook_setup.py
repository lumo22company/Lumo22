#!/usr/bin/env python3
"""
Check that the Stripe webhook endpoint is reachable and STRIPE_WEBHOOK_SECRET is set.
Run after you've set STRIPE_WEBHOOK_SECRET in Railway. Usage: python3 check_webhook_setup.py
"""
import os
import sys
import urllib.request

# Default to your Railway URL; override with BASE_URL in .env
from dotenv import load_dotenv
load_dotenv()
BASE = (os.getenv("BASE_URL") or "https://lumo-22-production.up.railway.app").strip().rstrip("/")
if BASE and not BASE.startswith("http"):
    BASE = "https://" + BASE
URL = f"{BASE}/webhooks/stripe"


def main():
    print(f"Checking: {URL}\n")
    try:
        req = urllib.request.Request(URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
    except Exception as e:
        print(f"ERROR: Could not reach the webhook URL.\n{e}")
        print("\nMake sure the app is deployed and BASE_URL (or the default) is correct.")
        sys.exit(1)

    if '"configured":true' in body or '"configured": true' in body:
        print("OK — Webhook endpoint is reachable and STRIPE_WEBHOOK_SECRET is set.")
        print("Stripe can verify signatures; intake emails should work after payment.")
        return
    if '"configured":false' in body or '"configured": false' in body:
        print("NOT SET — STRIPE_WEBHOOK_SECRET is missing or empty on the server.")
        print("\nDo this:")
        print("1. Stripe Dashboard → Developers → Webhooks → your endpoint → Reveal Signing secret")
        print("2. Copy the value (starts with whsec_...)")
        print("3. Railway → your service → Variables → set STRIPE_WEBHOOK_SECRET to that value")
        print("4. Redeploy, then run this script again.")
        sys.exit(1)
    print("Unexpected response:", body[:200])
    sys.exit(1)


if __name__ == "__main__":
    main()
