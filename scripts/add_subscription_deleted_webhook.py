#!/usr/bin/env python3
"""
Add customer.subscription.deleted to your Stripe event destination via the API.
Run: python scripts/add_subscription_deleted_webhook.py

Requires STRIPE_SECRET_KEY in .env (use your secret key, not publishable).
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests

STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY")
DESTINATION_NAME = "Lumo 22 captions"
ENDPOINT_URL = "https://lumo22.com/webhooks/stripe"

# Existing events (from your 3) + the new one
EVENTS = [
    "checkout.session.completed",
    "invoice.created",
    "invoice.paid",
    "customer.subscription.deleted",
]

def main():
    if not STRIPE_SECRET:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        sys.exit(1)

    base = "https://api.stripe.com"
    headers = {
        "Authorization": f"Bearer {STRIPE_SECRET}",
        "Stripe-Version": "2024-10-28.acacia",
        "Content-Type": "application/json",
    }

    # 1. List event destinations
    print("Listing event destinations...")
    r = requests.get(f"{base}/v2/core/event_destinations", headers=headers)
    if r.status_code != 200:
        print(f"ERROR listing: {r.status_code} {r.text}")
        sys.exit(1)

    data = r.json()
    dests = data.get("data", [])
    dest = None
    for d in dests:
        if d.get("name") == DESTINATION_NAME or (d.get("webhook_endpoint") or {}).get("url") == ENDPOINT_URL:
            dest = d
            break

    if not dest:
        print(f"Could not find event destination named '{DESTINATION_NAME}' or URL {ENDPOINT_URL}")
        print("Available destinations:")
        for d in dests:
            print(f"  - {d.get('name')} (id={d.get('id')})")
        sys.exit(1)

    dest_id = dest["id"]
    print(f"Found: {dest.get('name')} (id={dest_id})")
    print(f"Current events: {dest.get('enabled_events', [])}")

    # 2. Update with new events
    print(f"\nUpdating to events: {EVENTS}")
    update_r = requests.post(
        f"{base}/v2/core/event_destinations/{dest_id}",
        headers=headers,
        json={
            "enabled_events": EVENTS,
            "webhook_endpoint": {"url": ENDPOINT_URL},
            "name": DESTINATION_NAME,
            "description": "Sends payment completed to our app for 30 Days Captions.",
        },
    )

    if update_r.status_code != 200:
        print(f"ERROR updating: {update_r.status_code}")
        print(update_r.text)
        sys.exit(1)

    result = update_r.json()
    print(f"\nUpdated. New enabled_events: {result.get('enabled_events', [])}")
    print("Done. customer.subscription.deleted is now enabled.")

if __name__ == "__main__":
    main()
