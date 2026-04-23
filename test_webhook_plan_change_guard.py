#!/usr/bin/env python3
"""Regression tests for Stripe subscription.updated plan-change email guard."""

from unittest.mock import MagicMock

from api.webhooks import (
    _plan_change_dedupe_key,
    _should_send_plan_change_email,
)


def test_guard_skips_when_no_plan_delta_and_no_items_change():
    assert _should_send_plan_change_email({}, 2, True, 2, True) is False


def test_guard_sends_when_platforms_change():
    assert _should_send_plan_change_email({}, 1, False, 2, False) is True


def test_guard_sends_when_stories_toggle():
    assert _should_send_plan_change_email({}, 1, False, 1, True) is True


def test_guard_skips_if_stripe_reports_items_change_but_effective_plan_same():
    assert _should_send_plan_change_email({"items": {}}, 2, True, 2, True) is False


def test_plan_change_email_dedupe_key_is_stable():
    key = _plan_change_dedupe_key("sub_123", "User@Example.com", 3, False)
    assert key == "sub_123|user@example.com|3|0"


def test_billing_plan_change_helper_skips_when_db_claim_false(monkeypatch):
    """When try_claim_plan_change_confirmation_sent returns False, do not send email."""
    from api import billing_routes
    from services.notifications import NotificationService

    co_mock = MagicMock()
    co_mock.try_claim_plan_change_confirmation_sent.return_value = False

    monkeypatch.setattr("services.caption_order_service.CaptionOrderService", lambda: co_mock)
    sent = []

    def _fake_send(self, customer_email, **kwargs):
        sent.append((customer_email, kwargs))

    monkeypatch.setattr(NotificationService, "send_plan_change_confirmation_email", _fake_send)
    billing_routes._send_plan_change_confirmation_with_webhook_dedupe(
        "11111111-1111-1111-1111-111111111111",
        "sub_abcd",
        "client@example.com",
        2,
        False,
        change_summary="What changed: test.",
        when_effective="Next pack.",
        new_price_display="£1",
        old_price_display="£2",
        business_name="Biz",
    )
    assert sent == []
    co_mock.try_claim_plan_change_confirmation_sent.assert_called_once()


def test_billing_releases_plan_change_claim_when_send_returns_false(monkeypatch):
    """Failed SendGrid send clears DB claim so a later retry can email."""
    from api import billing_routes
    from services.notifications import NotificationService

    co_mock = MagicMock()
    co_mock.try_claim_plan_change_confirmation_sent.return_value = True
    released = []

    def _release(oid):
        released.append(oid)

    co_mock.release_plan_change_confirmation_claim.side_effect = _release
    monkeypatch.setattr("services.caption_order_service.CaptionOrderService", lambda: co_mock)
    monkeypatch.setattr(NotificationService, "send_plan_change_confirmation_email", lambda *a, **k: False)

    billing_routes._send_plan_change_confirmation_with_webhook_dedupe(
        "22222222-2222-2222-2222-222222222222",
        "sub_test",
        "x@y.com",
        2,
        True,
        change_summary="What changed: test.",
        when_effective="Next pack.",
        new_price_display="£1",
        old_price_display="£2",
        business_name=None,
    )
    assert released == ["22222222-2222-2222-2222-222222222222"]
