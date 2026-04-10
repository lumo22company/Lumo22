#!/usr/bin/env python3
"""History list: all archived packs + current; merge rows sharing stripe_subscription_id."""

from app import _history_delivered_entries


def test_one_subscription_row_archives_plus_current():
    orders = [
        {
            "id": "a",
            "token": "tok-a",
            "status": "delivered",
            "stripe_subscription_id": "sub_1",
            "captions_md": "current",
            "delivered_at": "2026-06-01T12:00:00Z",
            "delivery_archive": [
                {"delivered_at": "2026-04-01T12:00:00Z", "captions_md": "x", "include_stories": False},
                {"delivered_at": "2026-05-01T12:00:00Z", "captions_md": "y", "include_stories": False},
            ],
            "include_stories": False,
        }
    ]
    entries = _history_delivered_entries(orders)
    assert len(entries) == 3
    currents = [e for e in entries if e.get("archive_index") is None]
    assert len(currents) == 1
    assert currents[0]["token"] == "tok-a"


def test_duplicate_stripe_subscription_rows_all_packs_including_stale_current():
    """Two caption_orders rows with same sub id: all archives from both + each row's last delivered pack."""
    orders = [
        {
            "id": "old",
            "token": "tok-old",
            "status": "delivered",
            "stripe_subscription_id": "sub_x",
            "captions_md": "stale-md",
            "delivered_at": "2026-03-01T12:00:00Z",
            "updated_at": "2026-03-01T12:00:00Z",
            "delivery_archive": [
                {"delivered_at": "2026-01-01T12:00:00Z", "captions_md": "a", "include_stories": False},
            ],
            "include_stories": False,
        },
        {
            "id": "new",
            "token": "tok-new",
            "status": "delivered",
            "stripe_subscription_id": "sub_x",
            "captions_md": "current-md",
            "delivered_at": "2026-06-01T12:00:00Z",
            "updated_at": "2026-06-01T12:00:00Z",
            "delivery_archive": [
                {"delivered_at": "2026-04-01T12:00:00Z", "captions_md": "b", "include_stories": False},
                {"delivered_at": "2026-05-01T12:00:00Z", "captions_md": "c", "include_stories": False},
            ],
            "include_stories": False,
        },
    ]
    entries = _history_delivered_entries(orders)
    currents = [e for e in entries if e.get("archive_index") is None]
    assert len(currents) == 2
    by_tok = {e["token"]: e for e in currents}
    assert by_tok["tok-old"]["delivered_at"].startswith("2026-03-01")
    assert by_tok["tok-new"]["delivered_at"].startswith("2026-06-01")
    archived = [e for e in entries if e.get("archive_index") is not None]
    assert len(archived) == 3
    tokens_arch = {e["token"] for e in archived}
    assert tokens_arch == {"tok-old", "tok-new"}
    assert len(entries) == 5


def test_duplicate_subscription_rows_identical_current_deduped():
    """Two rows same sub + same delivery snapshot: one line."""
    md = "same-pack"
    ts = "2026-06-01T12:00:00Z"
    orders = [
        {
            "id": "old",
            "token": "tok-old",
            "status": "delivered",
            "stripe_subscription_id": "sub_x",
            "captions_md": md,
            "delivered_at": ts,
            "updated_at": "2026-06-01T11:00:00Z",
            "delivery_archive": [],
        },
        {
            "id": "new",
            "token": "tok-new",
            "status": "delivered",
            "stripe_subscription_id": "sub_x",
            "captions_md": md,
            "delivered_at": ts,
            "updated_at": "2026-06-01T12:00:00Z",
            "delivery_archive": [],
        },
    ]
    entries = _history_delivered_entries(orders)
    currents = [e for e in entries if e.get("archive_index") is None]
    assert len(currents) == 1
    assert currents[0]["token"] == "tok-new"


def test_one_off_orders_each_get_current():
    orders = [
        {
            "id": "o1",
            "token": "t1",
            "status": "delivered",
            "stripe_subscription_id": "",
            "captions_md": "a",
            "delivered_at": "2026-01-01T12:00:00Z",
            "delivery_archive": [],
        },
        {
            "id": "o2",
            "token": "t2",
            "status": "delivered",
            "stripe_subscription_id": None,
            "captions_md": "b",
            "delivered_at": "2026-02-01T12:00:00Z",
            "delivery_archive": [],
        },
    ]
    entries = _history_delivered_entries(orders)
    assert len(entries) == 2
    assert sum(1 for e in entries if e.get("archive_index") is None) == 2
