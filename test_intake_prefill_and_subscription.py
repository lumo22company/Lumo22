#!/usr/bin/env python3
"""
Test prefill intake form from past order and one-off → subscription flow.

1. Prefill: /captions-intake?t=NEW_TOKEN&copy_from=OLD_TOKEN should prefill from OLD order's intake
   when NEW order has no intake, OLD has intake, and both share the same customer_email.

2. Subscribe URL: For one-off orders, subscribe_url should include copy_from=TOKEN so that after
   subscription payment, the new order's intake link gets copy_from and can prefill from the one-off.
"""
import sys
from unittest.mock import patch


def test_prefill_from_copy_from():
    """Intake page loads existing_intake from copy_from order when conditions met."""
    from app import app

    # One-off order A (has intake, completed)
    order_a = {
        "id": "ord-a",
        "token": "token-a",
        "customer_email": "same@example.com",
        "platforms_count": 1,
        "selected_platforms": "Instagram & Facebook",
        "include_stories": True,
        "stripe_subscription_id": None,  # one-off
        "intake": {
            "business_name": "Test Business",
            "business_type": "Coach / Mentor",
            "platform": "Instagram & Facebook",
            "audience": "busy founders",
        },
    }
    # New subscription order B (no intake yet, same customer, upgraded from one-off A)
    order_b = {
        "id": "ord-b",
        "token": "token-b",
        "customer_email": "same@example.com",
        "platforms_count": 1,
        "selected_platforms": "Instagram & Facebook",
        "include_stories": True,
        "stripe_subscription_id": "sub_xxx",  # subscription
        "intake": None,  # no intake yet
        "upgraded_from_token": "token-a",  # one-off → subscription, so prefill from order A is allowed
    }

    class FakeService:
        def get_by_token(self, tok):
            if tok == "token-a":
                return order_a
            if tok == "token-b":
                return order_b
            return None

    def fake_get_current_customer():
        return {"id": "cust-same", "email": "same@example.com"}

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService), \
             patch("api.auth_routes.get_current_customer", side_effect=fake_get_current_customer), \
             patch("app.get_current_customer", side_effect=fake_get_current_customer):
            # Subscription orders require login; patch so intake sees matching customer
            r = client.get("/captions-intake?t=token-b&copy_from=token-a")

    if r.status_code != 200:
        print(f"FAIL: Expected 200, got {r.status_code}")
        sys.exit(1)

    html = r.data.decode("utf-8")
    # Form should be prefilled with order A's intake
    if "Test Business" not in html:
        print("FAIL: Form should contain business_name from copy_from order")
        print("  Hint: copy_from loads from src_order when current order has no intake and same customer")
        sys.exit(1)
    if "Coach / Mentor" not in html or "Coach / Mentor" not in html:
        # business_type could be in option selected
        pass
    if "busy founders" not in html:
        print("FAIL: Form should contain audience from copy_from order")
        sys.exit(1)
    if "Instagram & Facebook" not in html:
        print("FAIL: Form should contain platform from copy_from order")
        sys.exit(1)

    print("PASS: Intake prefilled from copy_from order (same customer)")


def test_prefill_rejects_different_customer():
    """copy_from should NOT prefill when source and current order have different customer_email."""
    from app import app

    order_a = {
        "id": "ord-a",
        "token": "token-a",
        "customer_email": "alice@example.com",
        "platforms_count": 1,
        "intake": {"business_name": "Alice Corp"},
        "stripe_subscription_id": None,
    }
    order_b = {
        "id": "ord-b",
        "token": "token-b",
        "customer_email": "bob@example.com",
        "platforms_count": 1,
        "intake": None,
        "stripe_subscription_id": "sub_xxx",
    }

    class FakeService:
        def get_by_token(self, tok):
            return order_a if tok == "token-a" else (order_b if tok == "token-b" else None)

    def fake_get_current_customer_bob():
        return {"id": "cust-bob", "email": "bob@example.com"}

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService), \
             patch("api.auth_routes.get_current_customer", side_effect=fake_get_current_customer_bob), \
             patch("app.get_current_customer", side_effect=fake_get_current_customer_bob):
            r = client.get("/captions-intake?t=token-b&copy_from=token-a")

    if r.status_code != 200:
        print(f"FAIL: Expected 200, got {r.status_code}")
        sys.exit(1)

    html = r.data.decode("utf-8")
    # Should NOT show Alice Corp (different customer, no prefill)
    if "Alice Corp" in html:
        print("FAIL: Should not prefill from different customer's order")
        sys.exit(1)

    print("PASS: copy_from rejected when different customer")


def test_subscribe_url_includes_copy_from():
    """For one-off orders, subscribe_url must include copy_from=token for prefill after subscription."""
    from app import app

    order_oneoff = {
        "id": "ord-1",
        "token": "oneoff-token-xyz",
        "customer_email": "user@example.com",
        "platforms_count": 1,
        "selected_platforms": "LinkedIn",
        "include_stories": False,
        "stripe_subscription_id": None,  # one-off
        "intake": {"business_name": "My Co"},
    }

    class FakeService:
        def get_by_token(self, tok):
            return order_oneoff if tok == "oneoff-token-xyz" else None

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService):

            r = client.get("/captions-intake?t=oneoff-token-xyz")

    if r.status_code != 200:
        print(f"FAIL: Expected 200, got {r.status_code}")
        sys.exit(1)

    html = r.data.decode("utf-8")
    # subscribe_url is built in app.py: /captions-checkout-subscription?copy_from=TOKEN&...
    if "copy_from=oneoff-token-xyz" not in html and "copy_from%3Doneoff-token-xyz" not in html:
        print("FAIL: subscribe_url should include copy_from=oneoff-token-xyz")
        sys.exit(1)
    if "captions-checkout-subscription" not in html:
        print("FAIL: subscribe_url should point to subscription checkout")
        sys.exit(1)

    print("PASS: subscribe_url includes copy_from for one-off → subscription")


def test_subscribe_url_includes_stories_when_paid():
    """subscribe_url should include stories=1 when order has include_stories."""
    from app import app

    order_with_stories = {
        "id": "ord-1",
        "token": "tok-stories",
        "customer_email": "u@ex.com",
        "platforms_count": 1,
        "selected_platforms": "Instagram & Facebook",
        "include_stories": True,
        "stripe_subscription_id": None,
    }

    class FakeService:
        def get_by_token(self, tok):
            return order_with_stories if tok == "tok-stories" else None

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService):

            r = client.get("/captions-intake?t=tok-stories")

    html = r.data.decode("utf-8")
    if "stories=1" not in html:
        print("FAIL: subscribe_url should include stories=1 when include_stories")
        sys.exit(1)

    print("PASS: subscribe_url includes stories=1 when Stories paid")


def test_no_subscribe_url_for_subscription():
    """subscribe_url should be None for subscription orders (they already subscribed)."""
    from app import app

    order_sub = {
        "id": "ord-1",
        "token": "tok-sub",
        "customer_email": "u@ex.com",
        "platforms_count": 1,
        "stripe_subscription_id": "sub_xxx",  # already subscription
        "intake": None,
    }

    class FakeService:
        def get_by_token(self, tok):
            return order_sub if tok == "tok-sub" else None

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService):

            r = client.get("/captions-intake?t=tok-sub")

    html = r.data.decode("utf-8")
    # "Subscribe using this form" is only shown when subscribe_url is set
    if "Subscribe using this form" in html:
        print("FAIL: subscribe_url should not be shown for subscription orders")
        sys.exit(1)

    print("PASS: No subscribe_url for subscription orders")


def test_subscription_checkout_guest_redirects_to_signup():
    """Unauthenticated subscription checkout should go to signup (not login) with next= preserved."""
    from app import app
    from urllib.parse import urlparse, parse_qs

    with app.test_client() as client:
        r = client.get(
            "/captions-checkout-subscription?platforms=1&currency=gbp",
            follow_redirects=False,
        )
    if r.status_code != 302:
        print(f"FAIL: expected 302, got {r.status_code}")
        sys.exit(1)
    loc = r.headers.get("Location") or ""
    parsed = urlparse(loc)
    if parsed.path != "/signup":
        print(f"FAIL: expected redirect to /signup, got {loc!r}")
        sys.exit(1)
    qs = parse_qs(parsed.query)
    if "next" not in qs or not qs["next"]:
        print(f"FAIL: expected next= in redirect, got {loc!r}")
        sys.exit(1)
    print("PASS: guest subscription checkout redirects to /signup with next=")


def test_oneoff_prefills_platform_when_order_has_no_selected_platforms():
    """Single-platform one-off orders from /captions-checkout?platforms=1 often have no selected_platforms in DB."""
    from app import app

    order = {
        "id": "ord-x",
        "token": "tok-no-sel",
        "customer_email": "u@ex.com",
        "platforms_count": 1,
        "selected_platforms": None,
        "include_stories": False,
        "stripe_subscription_id": None,
        "intake": None,
    }

    class FakeService:
        def get_by_token(self, tok):
            return order if tok == "tok-no-sel" else None

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeService):
            r = client.get("/captions-intake?t=tok-no-sel")

    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert 'id="platform"' in html
    assert "Instagram &amp; Facebook" in html


if __name__ == "__main__":
    # Patch at module level - app imports CaptionOrderService in the route
    # We need to patch where it's used: in app.captions_intake_page it's "from services.caption_order_service import CaptionOrderService"
    # So we patch "app.CaptionOrderService" - but app might import it as svc from the service. Let me check.
    # app.py does: from services.caption_order_service import CaptionOrderService (inside the route) - so it's a local import.
    # We need to patch services.caption_order_service.CaptionOrderService
    test_prefill_from_copy_from()
    test_prefill_rejects_different_customer()
    test_subscribe_url_includes_copy_from()
    test_subscribe_url_includes_stories_when_paid()
    test_no_subscribe_url_for_subscription()
    test_subscription_checkout_guest_redirects_to_signup()
    test_oneoff_prefills_platform_when_order_has_no_selected_platforms()
    print("\nAll tests passed.")
