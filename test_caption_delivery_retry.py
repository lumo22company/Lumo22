#!/usr/bin/env python3
"""Unit tests for first-pack delivery auto-retry rules (no Supabase)."""

from datetime import datetime, timedelta, timezone

from services.caption_delivery_recovery import (
    CAPTIONS_MAX_AUTO_DELIVERY_FAILURES,
    order_generating_attempt_reference,
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


def test_has_captions_md_never_retry_without_subscription():
    """One-off / first pack: existing md means delivered; do not auto-retry."""
    row = {
        "status": "failed",
        "captions_md": "## Day 1",
        "delivery_failure_count": 0,
    }
    assert row_needs_first_delivery_retry(row) is False


def test_subscription_failed_with_captions_md_needs_retry():
    row = {
        "status": "failed",
        "captions_md": "## Day 1",
        "delivery_failure_count": 0,
        "stripe_subscription_id": "sub_123",
    }
    assert row_needs_first_delivery_retry(row) is True


def test_subscription_generating_stale_with_captions_md_needs_retry():
    stale = datetime.now(timezone.utc) - timedelta(minutes=50)
    row = {
        "status": "generating",
        "captions_md": "## Previous month",
        "updated_at": _old(stale),
        "stripe_subscription_id": "sub_123",
    }
    assert row_needs_first_delivery_retry(row) is True


def test_subscription_delivered_with_md_no_retry():
    row = {
        "status": "delivered",
        "captions_md": "## Day 1",
        "stripe_subscription_id": "sub_123",
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
    stale = datetime.now(timezone.utc) - timedelta(minutes=50)
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


def test_generating_below_stale_threshold_no_retry():
    """Below STALE_GENERATING_RETRY_AFTER_MINUTES: do not auto-retry (may still be generating)."""
    ref = datetime.now(timezone.utc) - timedelta(minutes=40)
    row = {
        "status": "generating",
        "captions_md": "",
        "delivery_last_attempt_at": _old(ref),
        "updated_at": _old(datetime.now(timezone.utc)),
    }
    assert row_needs_first_delivery_retry(row) is False


def test_order_generating_attempt_reference_prefers_delivery_last_attempt_at():
    stale = datetime.now(timezone.utc) - timedelta(minutes=30)
    fresh = datetime.now(timezone.utc) - timedelta(seconds=30)
    row = {
        "delivery_last_attempt_at": _old(stale),
        "updated_at": _old(fresh),
        "created_at": _old(fresh),
    }
    assert order_generating_attempt_reference(row) == _old(stale)


def test_subscription_generating_stale_attempt_despite_recent_intake_save():
    """Intake-only save bumps updated_at; recovery should still see stale generation."""
    stale = datetime.now(timezone.utc) - timedelta(minutes=50)
    fresh_save = datetime.now(timezone.utc) - timedelta(minutes=1)
    row = {
        "status": "generating",
        "captions_md": "## Previous month",
        "delivery_last_attempt_at": _old(stale),
        "updated_at": _old(fresh_save),
        "stripe_subscription_id": "sub_123",
    }
    assert row_needs_first_delivery_retry(row) is True


def test_subscription_generating_fresh_attempt_no_retry_even_if_updated_at_is_new():
    recent_attempt = datetime.now(timezone.utc) - timedelta(minutes=3)
    fresh_save = datetime.now(timezone.utc) - timedelta(seconds=10)
    row = {
        "status": "generating",
        "captions_md": "## Previous month",
        "delivery_last_attempt_at": _old(recent_attempt),
        "updated_at": _old(fresh_save),
        "stripe_subscription_id": "sub_123",
    }
    assert row_needs_first_delivery_retry(row) is False
