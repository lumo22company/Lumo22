#!/usr/bin/env python3
"""Regression tests for Stripe subscription.updated plan-change email guard."""

from api.webhooks import (
    _mark_plan_change_email_sent,
    _plan_change_dedupe_key,
    _plan_change_email_dedupe,
    _plan_change_email_recently_sent,
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


def test_plan_change_email_dedupe_ttl_window():
    _plan_change_email_dedupe.clear()
    key = _plan_change_dedupe_key("sub_123", "user@example.com", 2, True)
    assert _plan_change_email_recently_sent(key, now_ts=1000.0) is False
    _mark_plan_change_email_sent(key, now_ts=1000.0)
    assert _plan_change_email_recently_sent(key, now_ts=1200.0) is True
    # After TTL (1 hour), it should no longer dedupe.
    assert _plan_change_email_recently_sent(key, now_ts=5000.0) is False
