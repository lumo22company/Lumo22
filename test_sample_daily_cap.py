#!/usr/bin/env python3
"""Rolling 24h cap on free sample generation (/api/captions-sample/start).

This is a spend cap, not a user-facing limit. Two properties matter:
  - it blocks before any order row is created, so AI cost has a hard ceiling
  - it fails open, so a Supabase failure never blocks real signups
"""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DISABLE_CSRF", "1")


class _FakeOrderService:
    """Stands in for CaptionOrderService. Records whether an order was created."""

    def __init__(self, count_since, has_sample=False):
        self._count_since = count_since
        self._has_sample = has_sample
        self.created = False

    def count_sample_orders_since(self, cutoff_iso):
        return self._count_since

    def has_sample_order_for_email(self, email):
        return self._has_sample

    def create_sample_order(self, email):
        self.created = True
        return {"token": "tok-123"}


def _post(client, fake, email="new@gmail.com"):
    with patch("services.caption_order_service.CaptionOrderService", return_value=fake), \
         patch("services.notifications.NotificationService") as notify:
        notify.return_value.send_sample_intake_link_email = MagicMock()
        return client.post("/api/captions-sample/start", json={"email": email})


def _client():
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def test_under_cap_creates_the_order():
    from config import Config

    client = _client()
    fake = _FakeOrderService(count_since=10)
    with patch.object(Config, "CAPTIONS_SAMPLE_DAILY_LIMIT", 50):
        resp = _post(client, fake)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert fake.created is True


def test_at_cap_blocks_before_creating_anything():
    from config import Config

    client = _client()
    fake = _FakeOrderService(count_since=50)
    with patch.object(Config, "CAPTIONS_SAMPLE_DAILY_LIMIT", 50):
        resp = _post(client, fake)
    assert resp.status_code == 429
    body = resp.get_json()
    assert body.get("cap_reached") is True
    # The point of the cap: no row, therefore no generation, therefore no spend.
    assert fake.created is False


def test_count_failure_fails_open():
    """None means 'couldn't determine' — allow the signup rather than block a customer."""
    from config import Config

    client = _client()
    fake = _FakeOrderService(count_since=None)
    with patch.object(Config, "CAPTIONS_SAMPLE_DAILY_LIMIT", 50):
        resp = _post(client, fake)
    assert resp.status_code == 200
    assert fake.created is True


def test_cap_of_zero_disables_the_check():
    from config import Config

    client = _client()
    fake = _FakeOrderService(count_since=10_000)
    with patch.object(Config, "CAPTIONS_SAMPLE_DAILY_LIMIT", 0):
        resp = _post(client, fake)
    assert resp.status_code == 200
    assert fake.created is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("All sample daily cap tests passed.")
