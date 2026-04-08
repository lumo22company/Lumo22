#!/usr/bin/env python3
"""Regression tests for intake launch-event date window validation."""

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

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            r = client.post("/api/captions-intake", json=payload)

    assert r.status_code == 400
    msg = (r.get_json() or {}).get("error", "")
    assert "outside your next 30-day captions window" in msg


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

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
            r = client.post("/api/captions-intake", json=payload)

    assert r.status_code == 400
    msg = (r.get_json() or {}).get("error", "")
    assert "Voice is required" in msg

