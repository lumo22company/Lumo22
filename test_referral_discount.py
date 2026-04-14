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


def test_self_referral_refund_calls_stripe_when_owner_matches_payer():
    from unittest.mock import patch
    from services.stripe_referral_promotion import refund_self_referral_promotion_discount_if_needed

    session = {
        "id": "cs_test_self_refund_001",
        "payment_intent": "pi_test_abc",
        "total_details": {"amount_discount": 970},
    }
    owner = {"id": "cust-owner", "email": "buyer@example.com"}

    with patch("services.stripe_referral_promotion.get_promotion_code_str_from_checkout_session", return_value="ABCD1234"):
        with patch("services.customer_auth_service.CustomerAuthService") as mock_auth_cls:
            mock_auth_cls.return_value.get_by_referral_code.return_value = owner
            with patch("services.stripe_referral_promotion.Config.STRIPE_SECRET_KEY", "sk_test"):
                with patch("stripe.Refund.create") as mock_refund:
                    refund_self_referral_promotion_discount_if_needed(session, payer_email="buyer@example.com")
    mock_refund.assert_called_once()
    kw = mock_refund.call_args[1]
    assert kw.get("payment_intent") == "pi_test_abc"
    assert kw.get("amount") == 970
    assert kw.get("idempotency_key") == "lumo-self-referral-discount-cs_test_self_refund_001"
    print("PASS: self-referral refund invoked when payer owns code")


def test_self_referral_refund_skips_when_payer_differs_from_owner():
    from unittest.mock import patch
    from services.stripe_referral_promotion import refund_self_referral_promotion_discount_if_needed

    session = {"id": "cs_test_002", "payment_intent": "pi_x", "total_details": {"amount_discount": 500}}
    owner = {"id": "o1", "email": "referrer@example.com"}

    with patch("services.stripe_referral_promotion.get_promotion_code_str_from_checkout_session", return_value="ZZZZ9999"):
        with patch("services.customer_auth_service.CustomerAuthService") as mock_auth_cls:
            mock_auth_cls.return_value.get_by_referral_code.return_value = owner
            with patch("services.stripe_referral_promotion.Config.STRIPE_SECRET_KEY", "sk_test"):
                with patch("stripe.Refund.create") as mock_refund:
                    refund_self_referral_promotion_discount_if_needed(session, payer_email="friend@example.com")
    mock_refund.assert_not_called()
    print("PASS: self-referral refund skipped when payer is not code owner")


if __name__ == "__main__":
    test_checkout_allows_promotion_codes_no_auto_discount()
    test_subscription_checkout_allows_promotion_codes()
    test_self_referral_refund_calls_stripe_when_owner_matches_payer()
    test_self_referral_refund_skips_when_payer_differs_from_owner()
    print("All referral checkout tests passed.")
