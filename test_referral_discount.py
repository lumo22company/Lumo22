#!/usr/bin/env python3
"""
Refer-a-friend: discounts are entered on Stripe Checkout (promotion codes), not auto-applied on Session.create.
"""
import sys
from unittest.mock import patch, MagicMock


def test_checkout_allows_promotion_codes_no_auto_discount():
    """Captions one-off checkout enables Stripe promotion codes; does not auto-apply coupon."""
    from app import app

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    with app.test_client() as client:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = fake_session
            r = client.get("/api/captions-checkout?platforms=1&ref=FRIEND01")
    if r.status_code != 302:
        print("FAIL: expected 302 redirect, got", r.status_code)
        sys.exit(1)
    call_kw = mock_create.call_args[1]
    if not call_kw.get("allow_promotion_codes"):
        print("FAIL: expected allow_promotion_codes=True, got", call_kw.get("allow_promotion_codes"))
        sys.exit(1)
    if call_kw.get("discounts"):
        print("FAIL: expected no automatic discounts, got", call_kw.get("discounts"))
        sys.exit(1)
    print("PASS: one-off checkout allows promotion codes, no auto discount")


def test_subscription_checkout_allows_promotion_codes():
    """Subscription checkout allows promotion codes."""
    from app import app
    from unittest.mock import patch, MagicMock

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    with app.test_client() as client:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = fake_session
            with patch("api.auth_routes.get_current_customer", return_value={"id": "u1", "email": "a@b.com"}):
                r = client.get("/api/captions-checkout-subscription?platforms=1")
    assert r.status_code == 302, r.status_code
    call_kw = mock_create.call_args[1]
    assert call_kw.get("allow_promotion_codes") is True
    assert not call_kw.get("discounts")
    print("PASS: subscription checkout allows promotion codes")


if __name__ == "__main__":
    test_checkout_allows_promotion_codes_no_auto_discount()
    test_subscription_checkout_allows_promotion_codes()
    print("All referral checkout tests passed.")
