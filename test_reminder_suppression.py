#!/usr/bin/env python3
"""Regression tests for reminder suppression rules."""

from services.caption_reminder_service import (
    _has_other_ready_or_completed_orders,
    _is_subscription_reminder_eligible,
)


def test_subscription_reminder_skips_canceled_and_cancel_at_period_end():
    assert _is_subscription_reminder_eligible({"status": "active"}) is True
    assert _is_subscription_reminder_eligible({"status": "trialing"}) is True
    assert _is_subscription_reminder_eligible({"status": "canceled"}) is False
    assert _is_subscription_reminder_eligible({"status": "active", "cancel_at_period_end": True}) is False
    assert _is_subscription_reminder_eligible({"status": "active", "canceled_at": 123}) is False
    assert _is_subscription_reminder_eligible({"status": "active", "pause_collection": {"behavior": "keep_as_draft"}}) is False


def test_awaiting_intake_reminder_suppressed_when_customer_has_completed_order():
    current = {"id": "ord-await", "customer_email": "x@example.com", "status": "awaiting_intake"}
    peers = [
        current,
        {"id": "ord-delivered", "customer_email": "x@example.com", "status": "delivered"},
    ]

    class FakeSvc:
        def get_by_customer_email(self, _email):
            return peers

    assert _has_other_ready_or_completed_orders(FakeSvc(), current) is True


def test_awaiting_intake_reminder_not_suppressed_when_only_other_pending_orders():
    current = {"id": "ord-1", "customer_email": "x@example.com", "status": "awaiting_intake"}
    peers = [
        current,
        {"id": "ord-2", "customer_email": "x@example.com", "status": "awaiting_intake", "intake": {}, "captions_md": ""},
    ]

    class FakeSvc:
        def get_by_customer_email(self, _email):
            return peers

    assert _has_other_ready_or_completed_orders(FakeSvc(), current) is False

