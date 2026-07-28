#!/usr/bin/env python3
"""
Campaign attribution: caption_orders.source has to survive the whole funnel, because it is the
only thing linking an ad click to a paid order. Landing page → sample signup, and landing page →
Stripe metadata → webhook → paid order row.

Run with: pytest test_campaign_attribution.py -v
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("DISABLE_CSRF", "1")

SOURCE = "google:cpc:us_launch"


def test_normalize_strips_junk_and_caps_length():
    from services.caption_order_service import normalize_attribution_source

    assert normalize_attribution_source("google:cpc:us_launch") == "google:cpc:us_launch"
    assert normalize_attribution_source("  ref:ABC123  ") == "ref:ABC123"
    # Arrives from a query string and ends up in reports, so tags stay to plain characters.
    # Angle brackets, quotes and ampersands go; "/" stays because campaign names use it.
    assert normalize_attribution_source("<script>alert(1)</script>") == "scriptalert1/script"
    assert normalize_attribution_source('a"b&c<d>') == "abcd"
    assert normalize_attribution_source("a" * 400) == "a" * 120
    assert normalize_attribution_source("") is None
    assert normalize_attribution_source(None) is None
    assert normalize_attribution_source("   ") is None


class _FakeSampleService:
    def __init__(self):
        self.source = "unset"

    def count_sample_orders_since(self, cutoff_iso):
        return 0

    def has_sample_order_for_email(self, email):
        return False

    def create_sample_order(self, email, currency="gbp", source=None):
        self.source = source
        return {"token": "tok-sample"}


def _post_sample(body):
    from app import app

    svc = _FakeSampleService()
    with patch("services.caption_order_service.CaptionOrderService", return_value=svc), \
         patch("services.notifications.NotificationService") as notify:
        notify.return_value.send_sample_intake_link_email = MagicMock()
        resp = app.test_client().post("/api/captions-sample/start", json=body)
    return resp, svc


def test_sample_signup_records_the_campaign():
    resp, svc = _post_sample({"email": "lead@gmail.com", "source": SOURCE})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert svc.source == SOURCE


def test_sample_signup_without_a_campaign_still_works():
    """Direct traffic has no tag; that must not block the signup."""
    resp, svc = _post_sample({"email": "lead@gmail.com"})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert svc.source in (None, "")


def _fake_stripe():
    captured = {"session_kwargs": None}

    def create_session(**kwargs):
        captured["session_kwargs"] = kwargs
        return SimpleNamespace(url="https://checkout.stripe.test/session")

    return SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create_session)),
    ), captured


def test_one_off_checkout_puts_source_in_stripe_metadata():
    from app import app
    import api.captions_routes as routes

    fake_stripe, captured = _fake_stripe()
    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_PRICE_ID", "price_test", create=True), \
             patch("api.auth_routes.get_current_customer", return_value=None), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(f"/api/captions-checkout?platforms=1&currency=usd&source={SOURCE}")

    assert r.status_code == 302
    assert ((captured["session_kwargs"] or {}).get("metadata") or {}).get("source") == SOURCE


def test_subscription_checkout_puts_source_in_stripe_metadata():
    from app import app
    import api.captions_routes as routes

    fake_stripe, captured = _fake_stripe()
    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", "price_sub", create=True), \
             patch("api.auth_routes.get_current_customer", return_value={"id": "c1", "email": "b@example.com"}), \
             patch.object(routes, "_customer_has_blocking_captions_subscription", return_value=False), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(f"/api/captions-checkout-subscription?platforms=1&currency=gbp&source={SOURCE}")

    assert r.status_code == 302
    assert ((captured["session_kwargs"] or {}).get("metadata") or {}).get("source") == SOURCE


def test_checkout_rejects_a_junk_source_without_failing_the_sale():
    """A malformed tag is cleaned, never a reason to lose the order."""
    from app import app
    import api.captions_routes as routes

    fake_stripe, captured = _fake_stripe()
    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_PRICE_ID", "price_test", create=True), \
             patch("api.auth_routes.get_current_customer", return_value=None), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get("/api/captions-checkout?platforms=1&currency=gbp&source=%3Cimg%20src%3Dx%3E")

    assert r.status_code == 302
    md = (captured["session_kwargs"] or {}).get("metadata") or {}
    assert "<" not in md.get("source", "") and ">" not in md.get("source", "")


def test_webhook_stamps_source_onto_the_paid_order():
    """The click → payment link: metadata written at checkout lands on the order row."""
    import api.webhooks as webhooks

    captured = {}

    class FakeOrderService:
        def get_by_stripe_session_id(self, sid):
            return None

        def get_by_customer_email(self, email):
            return []

        def get_by_token(self, token):
            return None

        def create_order(self, **kwargs):
            captured.update(kwargs)
            return {
                "id": "order-1",
                "token": "tok-new",
                "customer_email": kwargs.get("customer_email"),
                "intake": {},
            }

        def update(self, *a, **kw):
            return True

        def get_by_id(self, oid):
            return {"id": oid, "token": "tok-new", "intake": {}}

    session = {
        "id": "cs_test_attribution",
        "mode": "payment",
        "payment_status": "paid",
        "customer_details": {"email": "buyer@example.com"},
        "currency": "usd",
        "metadata": {"product": "captions", "platforms": "1", "source": SOURCE},
    }

    with patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
         patch("services.notifications.NotificationService") as notify:
        notify.return_value.send_email = MagicMock(return_value=True)
        notify.return_value.send_captions_intake_link_email = MagicMock(return_value=True)
        try:
            webhooks._handle_captions_payment(session)
        except Exception as e:
            # Downstream email/delivery steps are not what this test is about; the create call is.
            print(f"(downstream step raised, ignored: {e!r})")

    assert captured.get("source") == SOURCE, f"create_order kwargs were {captured}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL: {name}: {e}")
    sys.exit(1 if failures else 0)
