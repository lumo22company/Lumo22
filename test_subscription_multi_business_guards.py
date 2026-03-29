#!/usr/bin/env python3
"""
Regression tests for multi-business subscription guard hardening.
Run with: pytest test_subscription_multi_business_guards.py -v
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")


def _fake_stripe_for_checkout():
    captured = {"metadata": None, "session_kwargs": None}

    def create_session(**kwargs):
        captured["metadata"] = kwargs.get("metadata") or {}
        captured["session_kwargs"] = kwargs
        return SimpleNamespace(url="https://checkout.stripe.test/session")

    fake_stripe = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create_session)),
    )
    return fake_stripe, captured


def test_copy_from_requires_same_customer():
    """Upgrade checkout must reject copy_from token owned by another customer."""
    from app import app
    import api.captions_routes as routes

    class FakeOrderService:
        def get_by_token(self, token):
            if token == "tok-other":
                return {"token": "tok-other", "customer_email": "other@example.com", "status": "delivered"}
            return None

    fake_stripe, _captured = _fake_stripe_for_checkout()

    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", "price_test_sub", create=True), \
             patch("api.auth_routes.get_current_customer", return_value={"id": "cust-1", "email": "owner@example.com"}), \
             patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
             patch.object(routes, "_customer_has_blocking_captions_subscription", return_value=False), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(
                "/api/captions-checkout-subscription"
                "?copy_from=tok-other&platforms=1&currency=gbp&business_key=owner-biz"
            )

    assert r.status_code == 403
    payload = r.get_json() or {}
    assert "upgrade your own one-off order" in (payload.get("error") or "").lower()


def test_subscription_metadata_includes_business_context():
    """Checkout session metadata must include canonical business context."""
    from app import app
    import api.captions_routes as routes

    class FakeOrderService:
        def get_by_token(self, token):
            if token == "tok-owned":
                return {"token": "tok-owned", "customer_email": "owner@example.com", "status": "delivered"}
            return None

    fake_stripe, captured = _fake_stripe_for_checkout()

    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", "price_test_sub", create=True), \
             patch("api.auth_routes.get_current_customer", return_value={"id": "cust-1", "email": "owner@example.com"}), \
             patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
             patch.object(routes, "_customer_has_blocking_captions_subscription", return_value=False), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(
                "/api/captions-checkout-subscription"
                "?copy_from=tok-owned&platforms=1&currency=gbp&business_name=Acme Bakery&business_key=acme-bakery"
            )

    assert r.status_code == 302
    md = captured["metadata"] or {}
    assert md.get("copy_from") == "tok-owned"
    assert md.get("business_key") == "acme-bakery"
    assert md.get("business_name") == "Acme Bakery"


def test_one_off_to_subscription_checkout_prefills_email_and_subscription_mode():
    """
    One-off → subscription: logged-in user + copy_from matching their one-off order
    should create a Stripe Checkout session in subscription mode with customer_email set.
    """
    from app import app
    import api.captions_routes as routes

    class FakeOrderService:
        def get_by_token(self, token):
            if token == "tok-oneoff-abc":
                return {
                    "token": "tok-oneoff-abc",
                    "customer_email": "buyer@example.com",
                    "status": "delivered",
                    "delivered_at": "2026-01-01T12:00:00+00:00",
                }
            return None

    fake_stripe, captured = _fake_stripe_for_checkout()

    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", "price_test_sub", create=True), \
             patch(
                 "api.auth_routes.get_current_customer",
                 return_value={"id": "cust-1", "email": "buyer@example.com"},
             ), \
             patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
             patch.object(routes, "_customer_has_blocking_captions_subscription", return_value=False), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(
                "/api/captions-checkout-subscription"
                "?copy_from=tok-oneoff-abc&platforms=1&currency=gbp",
                follow_redirects=False,
            )

    assert r.status_code == 302
    assert (r.headers.get("Location") or "").startswith("https://checkout.stripe.test/")
    kw = captured.get("session_kwargs") or {}
    assert kw.get("mode") == "subscription"
    assert kw.get("customer_email") == "buyer@example.com"
    md = kw.get("metadata") or {}
    assert md.get("product") == "captions_subscription"
    assert md.get("copy_from") == "tok-oneoff-abc"
    assert "line_items" in kw


def test_checkout_page_add_stories_preserves_business_context():
    """Pre-checkout add-stories link keeps business_name/business_key params."""
    from app import app

    with app.test_client() as client:
        with patch("app.get_current_customer", return_value={"id": "cust-1", "email": "owner@example.com"}):
            r = client.get(
                "/captions-checkout-subscription"
                "?platforms=1&currency=gbp&business_name=Acme%20Bakery&business_key=acme-bakery"
            )

    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "business_name=Acme%20Bakery" in html
    assert "business_key=acme-bakery" in html


def test_unauthenticated_subscription_page_does_not_prefill_email_from_copy_from():
    """Signup redirect should not leak or prefill email via copy_from token."""
    from app import app

    with app.test_client() as client:
        with patch("app.get_current_customer", return_value=None):
            r = client.get("/captions-checkout-subscription?copy_from=tok-any")

    assert r.status_code == 302
    location = r.headers.get("Location") or ""
    assert "/signup?next=" in location
    assert "&email=" not in location
