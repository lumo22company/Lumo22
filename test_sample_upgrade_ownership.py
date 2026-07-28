#!/usr/bin/env python3
"""
Regression tests for sample → paid one-off upgrade ownership.

copy_from names a free sample order whose answers get carried into the paid order. The token
travels in a URL (emailed link, shared, pasted), so holding it is not proof of owning the sample:
the requester has to supply the sample's own address, either by being logged in as its owner or by
typing it on the checkout page. A token on its own must pull nothing across — not the sample
owner's email into the Stripe session, not their business name, not their intake.

Run with: pytest test_sample_upgrade_ownership.py -v
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")

SAMPLE_TOKEN = "tok-sample-victim"
SAMPLE_EMAIL = "victim@example.com"
SAMPLE_BUSINESS = "Victim Bakery"
ATTACKER_EMAIL = "attacker@example.com"

SAMPLE_ORDER = {
    "id": "order-sample-1",
    "token": SAMPLE_TOKEN,
    "customer_email": SAMPLE_EMAIL,
    "product_type": "sample_3",
    "status": "delivered",
    "currency": "gbp",
    "intake": {
        "business_name": SAMPLE_BUSINESS,
        "platform": "Instagram & Facebook",
        "audience": "Local families",
    },
}


class FakeOrderService:
    """Only knows the victim's sample row."""

    def get_by_token(self, token):
        return dict(SAMPLE_ORDER) if token == SAMPLE_TOKEN else None


def _fake_stripe_for_checkout():
    captured = {"session_kwargs": None}

    def create_session(**kwargs):
        captured["session_kwargs"] = kwargs
        return SimpleNamespace(url="https://checkout.stripe.test/session")

    fake_stripe = SimpleNamespace(
        api_key="",
        checkout=SimpleNamespace(Session=SimpleNamespace(create=create_session)),
    )
    return fake_stripe, captured


def _run_checkout(query, *, customer=None):
    """GET /api/captions-checkout with Stripe and the order service stubbed."""
    from app import app
    import api.captions_routes as routes

    fake_stripe, captured = _fake_stripe_for_checkout()
    with app.test_client() as client:
        with patch.object(routes.Config, "STRIPE_SECRET_KEY", "sk_test", create=True), \
             patch.object(routes.Config, "STRIPE_CAPTIONS_PRICE_ID", "price_test_oneoff", create=True), \
             patch("api.auth_routes.get_current_customer", return_value=customer), \
             patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
             patch.dict(sys.modules, {"stripe": fake_stripe}):
            r = client.get(f"/api/captions-checkout?{query}", follow_redirects=False)
    return r, (captured["session_kwargs"] or {})


def test_copy_from_someone_elses_sample_carries_nothing():
    """A bare token from a stranger must not seed metadata, email or business name."""
    r, kw = _run_checkout(f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp")

    assert r.status_code == 302
    md = kw.get("metadata") or {}
    assert "copy_from" not in md, "unowned sample token must not reach Stripe metadata"
    assert "business_name" not in md, "must not copy the sample owner's business name"
    assert "business_key" not in md
    assert "customer_email" not in kw, "must not pre-fill the sample owner's email"
    assert SAMPLE_EMAIL not in str(kw), "sample owner's email leaked into the checkout session"
    assert SAMPLE_BUSINESS not in str(kw)


def test_copy_from_with_wrong_email_carries_nothing():
    """Guessing at the sample's address must not unlock it either."""
    r, kw = _run_checkout(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp"
        f"&email={ATTACKER_EMAIL}&email_confirm={ATTACKER_EMAIL}"
    )

    assert r.status_code == 302
    md = kw.get("metadata") or {}
    assert "copy_from" not in md
    assert "business_name" not in md
    # The attacker's own address is still used for their checkout; the victim's is not.
    assert kw.get("customer_email") == ATTACKER_EMAIL
    assert SAMPLE_EMAIL not in str(kw)
    assert SAMPLE_BUSINESS not in str(kw)


def test_copy_from_ignored_when_logged_in_as_someone_else():
    """A logged-in account that does not own the sample proves nothing about it."""
    r, kw = _run_checkout(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp",
        customer={"id": "cust-2", "email": ATTACKER_EMAIL},
    )

    assert r.status_code == 302
    assert "copy_from" not in (kw.get("metadata") or {})
    assert SAMPLE_EMAIL not in str(kw)


def test_owner_upgrade_by_typed_email_works_end_to_end():
    """Normal path: the sample's own address typed at checkout carries the upgrade across."""
    r, kw = _run_checkout(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp"
        f"&email={SAMPLE_EMAIL}&email_confirm={SAMPLE_EMAIL}"
    )

    assert r.status_code == 302
    assert (r.headers.get("Location") or "").startswith("https://checkout.stripe.test/")
    md = kw.get("metadata") or {}
    assert md.get("copy_from") == SAMPLE_TOKEN, "owner's upgrade must still link to the sample"
    assert md.get("business_name") == SAMPLE_BUSINESS
    assert md.get("business_key") == "victim-bakery"
    assert md.get("product") == "captions"
    assert kw.get("mode") == "payment"
    assert kw.get("customer_email") == SAMPLE_EMAIL
    assert kw.get("line_items")


def test_owner_upgrade_while_logged_in_works():
    """Same-owner upgrade also works from an account session, with no email params."""
    r, kw = _run_checkout(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp",
        customer={"id": "cust-1", "email": SAMPLE_EMAIL.upper()},
    )

    assert r.status_code == 302
    md = kw.get("metadata") or {}
    assert md.get("copy_from") == SAMPLE_TOKEN
    assert md.get("business_name") == SAMPLE_BUSINESS
    assert kw.get("customer_email") == SAMPLE_EMAIL


def test_explicit_business_name_still_wins_for_owner():
    """A name typed on the checkout page is not overwritten by the sample's."""
    r, kw = _run_checkout(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp&business_name=New Trading Name"
        f"&email={SAMPLE_EMAIL}&email_confirm={SAMPLE_EMAIL}"
    )

    md = kw.get("metadata") or {}
    assert md.get("copy_from") == SAMPLE_TOKEN
    assert md.get("business_name") == "New Trading Name"


def _get_checkout_page(query, *, customer=None):
    from app import app

    with app.test_client() as client:
        with patch("app.get_current_customer", return_value=customer), \
             patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            r = client.get(f"/captions-checkout?{query}")
    return r, r.data.decode("utf-8")


def test_checkout_page_hides_sample_details_from_non_owner():
    """The pre-checkout page must not render the sample owner's details to a token holder."""
    r, html = _get_checkout_page(f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp")

    assert r.status_code == 200
    assert SAMPLE_BUSINESS not in html, "sample owner's business name rendered to a stranger"
    assert SAMPLE_EMAIL not in html
    # copy_from still travels to the API (which re-checks it), and we ask who they are.
    assert f"copy_from={SAMPLE_TOKEN}" in html
    assert 'id="checkout-sample-email"' in html


def test_checkout_page_prefills_business_name_for_owner():
    """Logged-in owner keeps the existing prefill and is not asked for their email again."""
    r, html = _get_checkout_page(
        f"copy_from={SAMPLE_TOKEN}&platforms=1&currency=gbp",
        customer={"id": "cust-1", "email": SAMPLE_EMAIL},
    )

    assert r.status_code == 200
    assert SAMPLE_BUSINESS in html
    assert 'id="checkout-sample-email"' not in html


def test_intake_page_does_not_prefill_from_sample_of_another_email():
    """
    Defence in depth behind the checkout fix: even with upgraded_from_token pointing at a sample
    (e.g. a row written before this guard existed), the intake form only merges the sample's
    answers when both orders belong to the same address.
    """
    from app import app

    paid_order = {
        "id": "order-paid-1",
        "token": "tok-paid",
        "customer_email": ATTACKER_EMAIL,
        "product_type": "standard",
        "status": "awaiting_intake",
        "platforms_count": 1,
        "selected_platforms": "Instagram & Facebook",
        "include_stories": False,
        "intake": {},
        "upgraded_from_token": SAMPLE_TOKEN,
        "stripe_subscription_id": "",
    }

    class Svc:
        def get_by_token(self, token):
            if token == "tok-paid":
                return dict(paid_order)
            return dict(SAMPLE_ORDER) if token == SAMPLE_TOKEN else None

        def has_subscription_upgraded_from_oneoff_token(self, token):
            return False

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", Svc), \
             patch("api.captions_routes.enrich_order_intake_from_checkout_session", side_effect=lambda svc, o: o), \
             patch("app.get_current_customer", return_value=None):
            r = client.get(f"/captions-intake?t=tok-paid&copy_from={SAMPLE_TOKEN}")

    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert SAMPLE_BUSINESS not in html, "sample intake leaked into another customer's form"
    assert "Local families" not in html
    assert SAMPLE_EMAIL not in html


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
