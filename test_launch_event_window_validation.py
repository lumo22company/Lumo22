#!/usr/bin/env python3
"""Regression tests for intake launch-event date window validation."""

from datetime import date
from unittest.mock import patch


def test_rejects_launch_date_outside_pack_window():
    from app import app

    class FakeOrderService:
        def get_by_token(self, token):
            return {
                "id": "ord-1",
                "token": "tok-1",
                "status": "awaiting_intake",
                "customer_email": "user@example.com",
                "include_stories": False,
                "platforms_count": 1,
                "pack_start_date": "2026-04-01",
                "intake": {},
            }

    payload = {
        "token": "tok-1",
        "business_name": "Acme",
        "voice_words": "warm, direct",
        "platform": "Instagram & Facebook",
        "goal": "More inquiries / leads",
        "launch_event_description": "Product launch 15 March",
    }

    anchor = (date(2026, 4, 1), "calendar_fallback", "Tuesday 1st April 2026")
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            with patch("api.captions_routes.compute_intake_pack_day1_anchor", return_value=anchor):
                r = client.post("/api/captions-intake", json=payload)

    assert r.status_code == 400
    msg = (r.get_json() or {}).get("error", "")
    assert "outside your next 30-day captions window" in msg


def test_rejects_any_date_outside_window_when_multi_dated():
    """Early-bird before pack start must fail even when summit range is in-window."""
    from app import app

    class FakeOrderService:
        def get_by_token(self, token):
            return {
                "id": "ord-1",
                "token": "tok-multi",
                "status": "awaiting_intake",
                "customer_email": "user@example.com",
                "include_stories": False,
                "platforms_count": 1,
                "pack_start_date": "2026-04-16",
                "intake": {},
            }

    payload = {
        "token": "tok-multi",
        "business_name": "Acme",
        "voice_words": "warm, direct",
        "platform": "Instagram & Facebook",
        "goal": "More inquiries / leads",
        "launch_event_description": (
            "Early-bird registration closes 8 April. Main two-day summit 18-19 April. "
            "Thank-you / replay session 25 April."
        ),
    }

    # Pin Day-1 anchor so the 30-day window in the error message does not depend on the runner's clock.
    anchor = (date(2026, 4, 16), "calendar_fallback", "Thursday 16th April 2026")
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            with patch("api.captions_routes.compute_intake_pack_day1_anchor", return_value=anchor):
                r = client.post("/api/captions-intake", json=payload)

    assert r.status_code == 400
    msg = (r.get_json() or {}).get("error", "")
    assert "outside your next 30-day captions window" in msg
    assert "May 2026" in msg
    assert "16 April" in msg


def test_rejects_empty_voice_words():
    """Voice is required for intake submit."""
    from app import app

    class FakeOrderService:
        def get_by_token(self, token):
            return {
                "id": "ord-1",
                "token": "tok-voice",
                "status": "awaiting_intake",
                "customer_email": "user@example.com",
                "include_stories": False,
                "platforms_count": 1,
                "pack_start_date": "2026-04-01",
                "intake": {},
            }

    payload = {
        "token": "tok-voice",
        "business_name": "Acme",
        "voice_words": "",
        "platform": "Instagram & Facebook",
        "goal": "More inquiries / leads",
    }

    anchor = (date(2026, 4, 1), "calendar_fallback", "Tuesday 1st April 2026")
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            with patch("api.captions_routes.compute_intake_pack_day1_anchor", return_value=anchor):
                r = client.post("/api/captions-intake", json=payload)

    assert r.status_code == 400
    msg = (r.get_json() or {}).get("error", "")
    assert "Voice is required" in msg

