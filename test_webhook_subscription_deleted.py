"""Tests for customer.subscription.deleted: clear Stripe sub link + subscription_cancelled_at."""

from unittest.mock import MagicMock, patch


def _event_deleted(sub_id: str = "sub_test_deleted_webhook") -> dict:
    return {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": sub_id, "customer": "cus_test"}},
    }


def test_subscription_deleted_clears_stripe_subscription_id_and_sets_cancelled_at():
    from app import app

    sub_id = "sub_test_deleted_webhook"
    order_row = {
        "id": "order-uuid-1",
        "token": "tok_test",
        "stripe_subscription_id": sub_id,
        "cancel_confirmation_sent_at": None,
    }
    updates_log = []

    class FakeOrderService:
        def get_by_stripe_subscription_id(self, sid):
            return order_row if sid == sub_id else None

        def update(self, order_id, updates):
            updates_log.append((str(order_id), dict(updates)))
            return True

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("stripe.Webhook.construct_event", return_value=_event_deleted(sub_id)):
                with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
                    with patch("api.webhooks._cancel_confirmation_already_sent", return_value=False):
                        with patch("api.webhooks._send_captions_subscription_cancelled_confirmation") as send_fn:
                            send_fn.return_value = order_row
                            resp = client.post(
                                "/webhooks/stripe",
                                data=b"{}",
                                headers={"Stripe-Signature": "t=1,v1=fake"},
                            )

    assert resp.status_code == 200
    assert send_fn.call_count == 1
    assert len(updates_log) == 1
    oid, upd = updates_log[0]
    assert oid == "order-uuid-1"
    assert upd.get("stripe_subscription_id") is None
    assert upd.get("subscription_cancelled_at")
    # Real CaptionOrderService.update adds updated_at; this fake receives the webhook dict only.


def test_subscription_deleted_skips_email_when_cancel_already_sent_still_clears_db():
    from app import app

    sub_id = "sub_test_dup_email"
    order_row = {
        "id": "order-uuid-2",
        "stripe_subscription_id": sub_id,
        "cancel_confirmation_sent_at": "2025-01-01T00:00:00Z",
    }

    updates_log = []

    class FakeOrderService:
        def get_by_stripe_subscription_id(self, sid):
            return order_row if sid == sub_id else None

        def update(self, order_id, updates):
            updates_log.append(dict(updates))
            return True

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("stripe.Webhook.construct_event", return_value=_event_deleted(sub_id)):
                with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
                    with patch("api.webhooks._cancel_confirmation_already_sent", return_value=True):
                        with patch("api.webhooks._send_captions_subscription_cancelled_confirmation") as send_fn:
                            resp = client.post(
                                "/webhooks/stripe",
                                data=b"{}",
                                headers={"Stripe-Signature": "t=1,v1=fake"},
                            )

    assert resp.status_code == 200
    send_fn.assert_not_called()
    assert len(updates_log) == 1
    assert updates_log[0].get("stripe_subscription_id") is None
    assert updates_log[0].get("subscription_cancelled_at")


def test_subscription_deleted_no_matching_order_returns_200_without_update():
    from app import app

    sub_id = "sub_unknown"

    class FakeOrderService:
        def get_by_stripe_subscription_id(self, sid):
            return None

        def update(self, order_id, updates):
            raise AssertionError("update should not run when no order")

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("stripe.Webhook.construct_event", return_value=_event_deleted(sub_id)):
                with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
                    with patch("api.webhooks._send_captions_subscription_cancelled_confirmation") as send_fn:
                        resp = client.post(
                            "/webhooks/stripe",
                            data=b"{}",
                            headers={"Stripe-Signature": "t=1,v1=fake"},
                        )

    assert resp.status_code == 200
    send_fn.assert_not_called()


def test_subscription_deleted_missing_column_falls_back_to_clear_subscription_only():
    from app import app

    sub_id = "sub_test_missing_col"
    order_row = {
        "id": "order-uuid-3",
        "stripe_subscription_id": sub_id,
    }
    calls = []

    class FakeOrderService:
        def get_by_stripe_subscription_id(self, sid):
            return order_row if sid == sub_id else None

        def update(self, order_id, updates):
            calls.append(dict(updates))
            if len(calls) == 1:
                raise Exception(
                    'PGRST204 "subscription_cancelled_at" not found in schema cache'
                )
            return True

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("stripe.Webhook.construct_event", return_value=_event_deleted(sub_id)):
                with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
                    with patch("api.webhooks._cancel_confirmation_already_sent", return_value=False):
                        with patch("api.webhooks._send_captions_subscription_cancelled_confirmation", return_value=None):
                            resp = client.post(
                                "/webhooks/stripe",
                                data=b"{}",
                                headers={"Stripe-Signature": "t=1,v1=fake"},
                            )

    assert resp.status_code == 200
    assert len(calls) == 2
    assert calls[0].get("stripe_subscription_id") is None
    assert "subscription_cancelled_at" in calls[0]
    assert calls[1].get("stripe_subscription_id") is None
    assert "subscription_cancelled_at" not in calls[1] or calls[1].get("subscription_cancelled_at") is None


def test_is_subscription_cancelled_at_column_missing_helper():
    from api.webhooks import _is_subscription_cancelled_at_column_missing

    assert _is_subscription_cancelled_at_column_missing(
        Exception('PGRST204 "subscription_cancelled_at"')
    )
    assert not _is_subscription_cancelled_at_column_missing(Exception("network error"))
