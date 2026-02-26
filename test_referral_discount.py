#!/usr/bin/env python3
"""
Test that referral discount (Stripe coupon) is applied at captions checkout when:
- ref= is in the URL and matches a valid referrer, or
- customer is logged in and has referred_by_customer_id set.
"""
import sys
from unittest.mock import patch, MagicMock


def test_referral_coupon_applied_when_ref_valid():
    """When ref=VALIDCODE is in query and referrer exists, Session.create is called with discounts."""
    from app import app
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    with app.test_client() as client:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = fake_session
            with patch("api.captions_routes._get_referral_coupon_id") as mock_get_coupon:
                mock_get_coupon.return_value = "coupon_referral10"
                r = client.get("/api/captions-checkout?platforms=1&ref=FRIEND01")
    if r.status_code != 302:
        print("FAIL: expected 302 redirect, got", r.status_code)
        sys.exit(1)
    call_kw = mock_create.call_args[1]
    if call_kw.get("discounts") != [{"coupon": "coupon_referral10"}]:
        print("FAIL: expected discounts=[{\"coupon\": \"coupon_referral10\"}], got", call_kw.get("discounts"))
        sys.exit(1)
    print("PASS: referral coupon applied when ref valid (mocked)")


def test_referral_coupon_not_applied_when_no_ref_no_referred_customer():
    """When no ref and no referred customer, Session.create is called without discounts."""
    from app import app
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    with app.test_client() as client:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = fake_session
            with patch("api.captions_routes._get_referral_coupon_id") as mock_get_coupon:
                mock_get_coupon.return_value = None
                r = client.get("/api/captions-checkout?platforms=1")
    if r.status_code != 302:
        print("FAIL: expected 302, got", r.status_code)
        sys.exit(1)
    call_kw = mock_create.call_args[1]
    if "discounts" in call_kw and call_kw["discounts"]:
        print("FAIL: expected no discounts, got", call_kw.get("discounts"))
        sys.exit(1)
    print("PASS: no referral discount when no ref / not referred (mocked)")


if __name__ == "__main__":
    test_referral_coupon_applied_when_ref_valid()
    test_referral_coupon_not_applied_when_no_ref_no_referred_customer()
    print("All referral discount tests passed.")
