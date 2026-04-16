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


def test_resolve_generation_uses_future_stored_anchor():
    from datetime import datetime, timedelta

    from api.captions_routes import resolve_pack_start_date_for_generation

    future = (datetime.utcnow().date() + timedelta(days=12)).strftime("%Y-%m-%d")
    assert resolve_pack_start_date_for_generation({"pack_start_date": future}) == future


def test_resolve_generation_bumps_stale_persisted_anchor_to_today():
    from datetime import datetime, timedelta

    from api.captions_routes import resolve_pack_start_date_for_generation

    past = (datetime.utcnow().date() - timedelta(days=6)).strftime("%Y-%m-%d")
    today = datetime.utcnow().date().strftime("%Y-%m-%d")
    assert resolve_pack_start_date_for_generation({"pack_start_date": past}) == today


def test_resolve_generation_empty_row_is_today():
    from datetime import datetime

    from api.captions_routes import resolve_pack_start_date_for_generation

    today = datetime.utcnow().date().strftime("%Y-%m-%d")
    assert resolve_pack_start_date_for_generation(None) == today
    assert resolve_pack_start_date_for_generation({}) == today


def test_format_intake_pack_window_range_same_month():
    from datetime import date

    from api.captions_routes import format_intake_pack_window_range_for_display

    s = format_intake_pack_window_range_for_display(date(2026, 5, 1))
    assert s == "1–30 May 2026"


def test_format_intake_pack_window_range_cross_month():
    from datetime import date

    from api.captions_routes import format_intake_pack_window_range_for_display

    s = format_intake_pack_window_range_for_display(date(2026, 5, 16))
    assert s == "16 May–14 June 2026"


def test_format_intake_pack_window_range_cross_year():
    from datetime import date

    from api.captions_routes import format_intake_pack_window_range_for_display

    s = format_intake_pack_window_range_for_display(date(2026, 12, 10))
    assert "December 2026" in s
    assert "January 2027" in s


def test_format_intake_pack_window_range_invalid_returns_empty():
    from api.captions_routes import format_intake_pack_window_range_for_display

    assert format_intake_pack_window_range_for_display(None) == ""
    assert format_intake_pack_window_range_for_display("x") == ""


def test_format_pack_cover_line_ordinal_utc_cross_month():
    from datetime import date

    from api.captions_routes import format_pack_cover_line_ordinal_utc

    s = format_pack_cover_line_ordinal_utc(date(2026, 5, 16))
    assert s.startswith("Your next pack covers ")
    assert "16th May 2026" in s
    assert "June 2026" in s
    assert s.endswith(".")
    assert "UTC" not in s


def test_format_pack_cover_line_ordinal_utc_same_month():
    from datetime import date

    from api.captions_routes import format_pack_cover_line_ordinal_utc

    s = format_pack_cover_line_ordinal_utc(date(2026, 5, 1))
    assert "1st May 2026" in s
    assert "30th May 2026" in s
