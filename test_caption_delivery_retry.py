#!/usr/bin/env python3
"""Unit tests for first-pack delivery auto-retry rules (no Supabase)."""

from datetime import datetime, timedelta, timezone

from services.caption_delivery_recovery import (
    CAPTIONS_MAX_AUTO_DELIVERY_FAILURES,
    row_needs_first_delivery_retry,
)


def _old(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def test_failed_below_cap_needs_retry():
    row = {
        "status": "failed",
        "captions_md": "",
        "delivery_failure_count": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES - 1,
    }
    assert row_needs_first_delivery_retry(row) is True


def test_failed_at_cap_does_not_retry():
    row = {
        "status": "failed",
        "captions_md": "",
        "delivery_failure_count": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES,
    }
    assert row_needs_first_delivery_retry(row) is False


def test_failed_zero_count_needs_retry():
    row = {"status": "failed", "captions_md": "", "delivery_failure_count": 0}
    assert row_needs_first_delivery_retry(row) is True


def test_delivered_with_empty_captions_still_false():
    row = {"status": "delivered", "captions_md": "", "delivery_failure_count": 0}
    assert row_needs_first_delivery_retry(row) is False


def test_has_captions_md_never_retry():
    row = {
        "status": "failed",
        "captions_md": "## Day 1",
        "delivery_failure_count": 0,
    }
    assert row_needs_first_delivery_retry(row) is False


def test_future_scheduled_not_retry():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    row = {
        "status": "failed",
        "captions_md": "",
        "delivery_failure_count": 0,
        "scheduled_delivery_at": future.isoformat(),
    }
    assert row_needs_first_delivery_retry(row) is False


def test_intake_completed_old_needs_retry():
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    row = {
        "status": "intake_completed",
        "captions_md": "",
        "updated_at": _old(old),
    }
    assert row_needs_first_delivery_retry(row, intake_completed_grace_seconds=120) is True


def test_intake_completed_fresh_skipped_grace():
    fresh = datetime.now(timezone.utc) - timedelta(seconds=30)
    row = {
        "status": "intake_completed",
        "captions_md": "",
        "updated_at": _old(fresh),
    }
    assert row_needs_first_delivery_retry(row, intake_completed_grace_seconds=120) is False


def test_generating_stuck_needs_retry():
    stale = datetime.now(timezone.utc) - timedelta(minutes=30)
    row = {
        "status": "generating",
        "captions_md": "",
        "updated_at": _old(stale),
    }
    assert row_needs_first_delivery_retry(row) is True


def test_generating_recent_no_retry():
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    row = {
        "status": "generating",
        "captions_md": "",
        "updated_at": _old(recent),
    }
    assert row_needs_first_delivery_retry(row) is False
