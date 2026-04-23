#!/usr/bin/env python3
"""
Ensure Stripe sends the events Lumo's /webhooks/stripe handler needs.

Updates an existing WebhookEndpoint (same URL) by merging enabled_events.
Does not create an endpoint unless you pass --create (then prints whsec once — add to Railway as STRIPE_WEBHOOK_SECRET).

Events wired in api/webhooks.py:
  checkout.session.completed, invoice.paid, invoice.created,
  customer.subscription.deleted, customer.subscription.updated

Usage (from project root):
  python3 scripts/ensure_stripe_webhook_endpoint.py --dry-run
  python3 scripts/ensure_stripe_webhook_endpoint.py --apply
  python3 scripts/ensure_stripe_webhook_endpoint.py --webhook-url https://YOUR.railway.app/webhooks/stripe --apply

Optional:
  STRIPE_WEBHOOK_PUBLIC_URL — full webhook URL if BASE_URL is localhost but Stripe should hit Railway.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from config import Config

REQUIRED_EVENTS = [
    "checkout.session.completed",
    "invoice.paid",
    "invoice.created",
    "customer.subscription.deleted",
    "customer.subscription.updated",
]


def _default_webhook_url() -> str:
    explicit = (os.environ.get("STRIPE_WEBHOOK_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit if explicit.endswith("/webhooks/stripe") else f"{explicit}/webhooks/stripe"
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://localhost") and not base.startswith("http://127.0.0.1"):
        return f"{base}/webhooks/stripe"
    return "https://lumo-22-production.up.railway.app/webhooks/stripe"


def _pick_endpoint(endpoints, want_url: str):
    """Exact URL match only (avoids picking www.lumo22.com when user asked for Railway)."""
    want = want_url.rstrip("/").lower()
    matches = []
    for ep in endpoints.data or []:
        u = (ep.url or "").rstrip("/").lower()
        if u == want:
            matches.append(ep)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        for ep in matches:
            if "railway.app" in (ep.url or "").lower() or "lumo22.com" in (ep.url or "").lower():
                return ep
        return matches[0]
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--webhook-url", default="", help="Full URL POST target (default: from BASE_URL or Railway)")
    ap.add_argument("--dry-run", action="store_true", help="Print only; do not call Stripe modify/create")
    ap.add_argument("--apply", action="store_true", help="Modify or create endpoint in Stripe")
    ap.add_argument(
        "--create",
        action="store_true",
        help="If no endpoint matches --webhook-url, create one (prints signing secret once)",
    )
    args = ap.parse_args()

    sk = (Config.STRIPE_SECRET_KEY or os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not sk:
        print("ERROR: STRIPE_SECRET_KEY not set in environment.")
        sys.exit(1)

    import stripe

    stripe.api_key = sk
    mode = "live" if sk.startswith("sk_live") else "test"
    want_url = (args.webhook_url or "").strip() or _default_webhook_url()

    print(f"Stripe mode: {mode}")
    print(f"Target webhook URL: {want_url}\n")

    endpoints = stripe.WebhookEndpoint.list(limit=100)
    ep = _pick_endpoint(endpoints, want_url)

    if not ep and args.create and args.apply:
        merged = sorted(set(REQUIRED_EVENTS))
        print(f"Creating webhook endpoint → {want_url}")
        created = stripe.WebhookEndpoint.create(
            url=want_url,
            enabled_events=merged,
            description="Lumo 22 captions (ensure_stripe_webhook_endpoint.py)",
        )
        secret = getattr(created, "secret", None) or (created.get("secret") if isinstance(created, dict) else None)
        print("Created endpoint id:", getattr(created, "id", None) or created.get("id"))
        print("ENABLED_EVENTS:", merged)
        if secret:
            print("\n*** Add to Railway (and local .env if needed) as STRIPE_WEBHOOK_SECRET ***")
            print(secret)
        else:
            print("\n(No signing secret in API response — copy from Stripe Dashboard → Webhooks → endpoint.)")
        sys.exit(0)

    if not ep:
        print("No existing Stripe webhook endpoint matches this URL.")
        print("Either:")
        print("  1) Stripe Dashboard → Developers → Webhooks → Add endpoint →", want_url)
        print("  2) Re-run with correct --webhook-url if your app uses another host")
        print("  3) Re-run with --create --apply to create via API (then set STRIPE_WEBHOOK_SECRET)")
        sys.exit(1)

    cur = list(ep.enabled_events or [])
    if "*" in cur or cur == ["*"]:
        print(f"Endpoint {ep.url!r} uses wildcard events — nothing to merge.")
        sys.exit(0)

    merged = sorted(set(cur) | set(REQUIRED_EVENTS))
    added = [e for e in REQUIRED_EVENTS if e not in cur]
    if not added:
        print(f"Endpoint {ep.id} {ep.url!r} already includes all required events.")
        print("Enabled:", sorted(cur))
        sys.exit(0)

    print(f"Endpoint {ep.id} {ep.url!r}")
    print("Will add events:", added)
    print("Full enabled_events after merge:", merged)

    if args.dry_run or not args.apply:
        print("\nPass --apply to update this endpoint in Stripe (omit --dry-run).")
        sys.exit(0)

    stripe.WebhookEndpoint.modify(ep.id, enabled_events=merged)
    print("\nOK: Stripe webhook endpoint updated.")


if __name__ == "__main__":
    main()
