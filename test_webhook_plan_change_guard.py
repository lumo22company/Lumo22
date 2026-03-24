#!/usr/bin/env python3
"""Regression tests for Stripe subscription.updated plan-change email guard."""

from api.webhooks import _should_send_plan_change_email


def test_guard_skips_when_no_plan_delta_and_no_items_change():
    assert _should_send_plan_change_email({}, 2, True, 2, True) is False


def test_guard_sends_when_platforms_change():
    assert _should_send_plan_change_email({}, 1, False, 2, False) is True


def test_guard_sends_when_stories_toggle():
    assert _should_send_plan_change_email({}, 1, False, 1, True) is True


def test_guard_sends_if_stripe_reports_items_change():
    assert _should_send_plan_change_email({"items": {}}, 2, True, 2, True) is True
