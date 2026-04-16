#!/usr/bin/env python3
"""Tests for compute_intake_pack_day1_anchor (intake Day 1 hint + validation alignment)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def test_pack_sooner_session_uses_today():
    from api.captions_routes import compute_intake_pack_day1_anchor

    order = {"stripe_subscription_id": "sub_x", "pack_start_date": "2026-04-01"}
    d, src, _disp = compute_intake_pack_day1_anchor(order, is_pack_sooner_edit_session=True)
    assert src == "pack_sooner"
    assert d == datetime.utcnow().date()


def test_scheduled_first_pack_when_future():
    from api.captions_routes import compute_intake_pack_day1_anchor

    order = {
        "scheduled_delivery_at": "2030-06-01T12:00:00Z",
        "stripe_subscription_id": "sub_x",
    }
    d, src, disp = compute_intake_pack_day1_anchor(order, is_pack_sooner_edit_session=False)
    assert src == "scheduled_first_pack"
    assert d.year == 2030 and d.month == 6 and d.day == 1
    assert "June" in disp or "2030" in disp


def test_stripe_renewal_uses_current_period_end():
    from api.captions_routes import compute_intake_pack_day1_anchor

    period_end = int(datetime(2031, 3, 15, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    sub = MagicMock()
    sub.get = lambda k, d=None: period_end if k == "current_period_end" else d

    order = {"stripe_subscription_id": "sub_test123", "pack_start_date": "2026-04-01"}
    with patch("api.captions_routes.Config.STRIPE_SECRET_KEY", "sk_test_fake"):
        with patch("stripe.Subscription.retrieve", return_value=sub):
            d, src, disp = compute_intake_pack_day1_anchor(order, is_pack_sooner_edit_session=False)
    assert src == "stripe_renewal"
    assert d.year == 2031 and d.month == 3 and d.day == 15


def test_explainer_stripe_renewal():
    from api.captions_routes import intake_pack_day1_explainer_for_source

    s = intake_pack_day1_explainer_for_source("stripe_renewal")
    assert "Stripe" in s or "renewal" in s.lower()
