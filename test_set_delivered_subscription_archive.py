#!/usr/bin/env python3
"""Subscription renewals: previous pack must append to delivery_archive even when status is 'generating'."""

from unittest.mock import MagicMock

from services.caption_order_service import CaptionOrderService


def test_set_delivered_archives_prior_pack_when_status_is_generating():
    """
    Renewal pipeline calls set_generating() before AI; set_delivered sees status 'generating'
    while captions_md still holds the previous month — archive must run (regression: was only 'delivered').
    """
    svc = CaptionOrderService.__new__(CaptionOrderService)
    captured = {}

    def fake_get_by_id(oid):
        return {
            "id": oid,
            "stripe_subscription_id": "sub_test123",
            "status": "generating",
            "delivered_at": "2026-01-15T12:00:00Z",
            "captions_md": "PREVIOUS_PACK_CONTENT",
            "delivery_archive": [],
            "captions_pdf_base64": "",
            "stories_pdf_base64": "",
            "include_stories": False,
            "intake": {},
        }

    def fake_update(oid, updates):
        captured["updates"] = updates
        return True

    svc.get_by_id = fake_get_by_id
    svc.update = fake_update

    ok = CaptionOrderService.set_delivered(
        svc,
        "order-uuid-1",
        "NEW_PACK_CONTENT_DIFFERENT",
        stories_pdf_bytes=None,
        captions_pdf_bytes=None,
    )
    assert ok is True
    assert "delivery_archive" in captured["updates"]
    arch = captured["updates"]["delivery_archive"]
    assert len(arch) == 1
    assert arch[0]["captions_md"] == "PREVIOUS_PACK_CONTENT"
    assert arch[0]["delivered_at"] == "2026-01-15T12:00:00Z"


def test_set_delivered_archives_even_when_new_md_equals_previous():
    """Regression: History must not collapse to one row if model output matches prior pack."""
    svc = CaptionOrderService.__new__(CaptionOrderService)
    captured = {}

    def fake_get_by_id(oid):
        return {
            "id": oid,
            "stripe_subscription_id": "sub_test123",
            "status": "generating",
            "delivered_at": "2026-01-15T12:00:00Z",
            "captions_md": "SAME_CONTENT",
            "delivery_archive": [],
            "captions_pdf_base64": "",
            "stories_pdf_base64": "",
            "include_stories": False,
            "intake": {},
        }

    def fake_update(oid, updates):
        captured["updates"] = updates
        return True

    svc.get_by_id = fake_get_by_id
    svc.update = fake_update

    ok = CaptionOrderService.set_delivered(
        svc,
        "order-uuid-eq",
        "SAME_CONTENT",
        stories_pdf_bytes=None,
        captions_pdf_bytes=None,
    )
    assert ok is True
    assert "delivery_archive" in captured["updates"]
    assert len(captured["updates"]["delivery_archive"]) == 1
    assert captured["updates"]["delivery_archive"][0]["captions_md"] == "SAME_CONTENT"


def test_set_delivered_does_not_archive_first_pack_under_generating():
    """No prior delivery — nothing to archive."""
    svc = CaptionOrderService.__new__(CaptionOrderService)
    captured = {}

    def fake_get_by_id(oid):
        return {
            "id": oid,
            "stripe_subscription_id": "sub_test123",
            "status": "generating",
            "delivered_at": "",
            "captions_md": "",
            "delivery_archive": [],
        }

    def fake_update(oid, updates):
        captured["updates"] = updates
        return True

    svc.get_by_id = fake_get_by_id
    svc.update = fake_update

    ok = CaptionOrderService.set_delivered(svc, "order-uuid-2", "FIRST_PACK", stories_pdf_bytes=None, captions_pdf_bytes=None)
    assert ok is True
    assert "delivery_archive" not in captured.get("updates", {})


def test_set_delivered_archives_one_off_redelivery():
    """One-off orders: second delivery archives the first so History can show both."""
    svc = CaptionOrderService.__new__(CaptionOrderService)
    captured = {}

    def fake_get_by_id(oid):
        return {
            "id": oid,
            "stripe_subscription_id": "",
            "status": "delivered",
            "delivered_at": "2026-02-01T12:00:00Z",
            "captions_md": "ONE_OFF_V1",
            "delivery_archive": [],
            "captions_pdf_base64": "YWFh",
            "stories_pdf_base64": "",
            "include_stories": False,
            "intake": {"business_name": "Test Co"},
        }

    def fake_update(oid, updates):
        captured["updates"] = updates
        return True

    svc.get_by_id = fake_get_by_id
    svc.update = fake_update

    ok = CaptionOrderService.set_delivered(
        svc,
        "order-oneoff-1",
        "ONE_OFF_V2",
        stories_pdf_bytes=None,
        captions_pdf_bytes=None,
    )
    assert ok is True
    assert "delivery_archive" in captured["updates"]
    arch = captured["updates"]["delivery_archive"]
    assert len(arch) == 1
    assert arch[0]["captions_md"] == "ONE_OFF_V1"
    assert arch[0]["delivered_at"] == "2026-02-01T12:00:00Z"
