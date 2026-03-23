#!/usr/bin/env python3
"""
Verify Stripe sends events needed for cancellation confirmation emails.

Run from project root:
  python3 scripts/check_cancel_subscription_email_setup.py

Requires STRIPE_SECRET_KEY in .env.

App handlers: api/webhooks.py
  - customer.subscription.updated
  - customer.subscription.deleted
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

REQUIRED_EVENTS = frozenset(
    {
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def _covers_cancellation(evs: list | None) -> tuple[bool, str]:
    if not evs:
        return False, "no enabled_events"
    s = set(evs)
    if "*" in s:
        return True, "all events (*)"
    missing = REQUIRED_EVENTS - s
    if not missing:
        return True, "required events enabled"
    return False, f"missing: {', '.join(sorted(missing))}"


def main() -> int:
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not key:
        print("ERROR: STRIPE_SECRET_KEY not set in .env")
        return 1

    import stripe

    stripe.api_key = key

    do_fix = "--fix" in sys.argv

    print("Stripe webhook endpoints vs cancellation email requirements\n")
    print(f"Required events: {', '.join(sorted(REQUIRED_EVENTS))}\n")

    try:
        endpoints = stripe.WebhookEndpoint.list(limit=100)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    rows = getattr(endpoints, "data", None) or []
    if not rows:
        print("No webhook endpoints in this Stripe account.")
        return 1

    app_hits = []
    to_patch: list[tuple[object, str, list]] = []  # (ep, url, new_evs)

    for ep in rows:
        url = (getattr(ep, "url", None) or "") or ""
        evs = list(getattr(ep, "enabled_events", None) or [])
        ok, reason = _covers_cancellation(evs)
        is_app = "/webhooks/stripe" in url
        line = f"  {'→' if is_app else ' '} {url or '(no url)'}\n     {reason}"
        if is_app:
            app_hits.append((ok, line))
            if not ok and "*" not in set(evs):
                merged = sorted(set(evs) | REQUIRED_EVENTS)
                to_patch.append((ep, url, merged))
        print(line)
        print()

    if app_hits:
        if all(h[0] for h in app_hits):
            print("OK: Your /webhooks/stripe endpoint(s) include cancellation events (or *).")
        else:
            print("FIX: Open Stripe → Developers → Webhooks → your endpoint → Add events:")
            print(f"   {', '.join(sorted(REQUIRED_EVENTS))}")
            print("Or run:  python3 scripts/check_cancel_subscription_email_setup.py --fix")
            if do_fix and to_patch:
                for ep, url, merged in to_patch:
                    eid = getattr(ep, "id", None)
                    if not eid:
                        continue
                    print(f"\n--fix: updating {eid} ({url}) …")
                    try:
                        stripe.WebhookEndpoint.modify(eid, enabled_events=merged)
                        print(f"  enabled_events now include: {sorted(REQUIRED_EVENTS)}")
                    except Exception as e:
                        print(f"  ERROR: {e}")
                        return 1
                print("\nRe-run without --fix to verify.")
                return 0
            return 1
    else:
        print("No URL containing /webhooks/stripe — confirm BASE_URL in Stripe matches your app.")
        return 1

    print("\nNext: Railway logs → search: cancel confirmation | SendGrid")
    print("Stripe → Webhooks → Recent deliveries → filter subscription.updated / deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
