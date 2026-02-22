#!/usr/bin/env python3
"""
Add invoice.paid to Stripe webhook endpoint.
Run once: python scripts/add_invoice_paid_to_stripe_webhook.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
if not stripe_key:
    print("STRIPE_SECRET_KEY not set")
    exit(1)

import stripe
stripe.api_key = stripe_key

# List endpoints
endpoints = stripe.WebhookEndpoint.list(limit=20)
if not endpoints.data:
    print("No webhook endpoints found")
    exit(1)

# Find the one that points to our app (lumo22.com or railway)
target = None
for ep in endpoints.data:
    url = (ep.url or "").lower()
    if "lumo22.com" in url or "railway.app" in url:
        if "/webhooks/stripe" in url or "stripe" in url:
            target = ep
            break
if not target:
    target = endpoints.data[0]
    print(f"Using first endpoint: {target.url}")

events = list(target.enabled_events or [])
if "invoice.paid" in events:
    print(f"invoice.paid already enabled on {target.url}")
    exit(0)

events.append("invoice.paid")
stripe.WebhookEndpoint.modify(target.id, enabled_events=events)
print(f"Added invoice.paid to {target.url}")
print(f"Enabled events: {events}")
