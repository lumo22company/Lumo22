#!/usr/bin/env python3
"""Regression test: get_pack_now immediate delivery uses upgraded platform/stories settings."""

from unittest.mock import MagicMock, patch


def test_get_pack_now_copies_intake_with_subscription_overrides():
    from app import app

    session_id = "cs_test_get_pack_now_sync"
    copy_from_token = "base_one_off_token"
    subscription_order = {
        "id": "sub-order-1",
        "stripe_subscription_id": "sub_123",
        "stripe_session_id": session_id,
        "selected_platforms": "LinkedIn, Pinterest",
        "include_stories": False,
    }
    one_off_order = {
        "id": "oneoff-order-1",
        "token": copy_from_token,
        "intake": {
            "business_name": "Demo Dental",
            "platform": "Instagram & Facebook, TikTok",
            "include_stories": True,
        },
    }

    class FakeOrderService:
        last_saved = None

        def get_by_id(self, oid):
            if str(subscription_order.get("id")) == str(oid):
                return subscription_order
            return None

        def get_by_stripe_session_id(self, sid):
            return subscription_order if sid == session_id else None

        def get_by_token(self, token):
            return one_off_order if token == copy_from_token else None

        def save_intake(self, order_id, intake, scheduled_delivery_at=None, pack_start_date=None):
            FakeOrderService.last_saved = {"order_id": order_id, "intake": dict(intake)}
            return True

        # Mirror real CaptionOrderService API used by the route so tests do not
        # raise and emit false operational alerts.
        def try_claim_immediate_pack_dispatch(self, order_id):
            return True

        def clear_immediate_pack_dispatch_claim(self, order_id):
            return None

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "subscription",
                "subscription": "sub_123",
                "payment_status": "paid",
                "amount_total": 15300,
                "metadata": {
                    "product": "captions_subscription",
                    "get_pack_now": "1",
                    "copy_from": copy_from_token,
                },
            }
        },
    }

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("stripe.Webhook.construct_event", return_value=event):
                with patch("api.webhooks._is_captions_payment", return_value=False):
                    with patch("api.webhooks._is_captions_subscription_payment", return_value=True):
                        with patch("api.webhooks._handle_captions_payment", return_value=None):
                            with patch("services.caption_order_service.CaptionOrderService", FakeOrderService):
                                with patch("threading.Thread") as mock_thread:
                                    mock_thread.return_value = MagicMock(start=lambda: None, daemon=False)
                                    resp = client.post(
                                        "/webhooks/stripe",
                                        data=b"{}",
                                        headers={"Stripe-Signature": "t=1,v1=fake"},
                                    )

    assert resp.status_code == 200
    assert FakeOrderService.last_saved is not None
    assert FakeOrderService.last_saved["order_id"] == "sub-order-1"
    saved = FakeOrderService.last_saved["intake"]
    # Critical regression guard:
    # do not keep stale one-off platform/stories when get_pack_now subscription settings differ.
    assert saved.get("platform") == "LinkedIn, Pinterest"
    assert saved.get("include_stories") is False


def test_captions_checkout_webhook_500_when_no_order_row_after_handler():
    """
    After checkout.session.completed runs _handle_captions_payment, a caption_orders row must exist
    for that session (all upgrade / one-off paths). Missing row → 500 for Stripe retries + ops alert.
    """
    from app import app

    session_id = "cs_test_missing_order_after_handler"

    class FakeOrderServiceNoRow:
        def get_by_stripe_session_id(self, sid):
            return None

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "subscription",
                "subscription": "sub_guard_1",
                "payment_status": "paid",
                "amount_total": 7900,
                "metadata": {"product": "captions_subscription"},
            }
        },
    }

    with app.test_client() as client:
        with patch("api.webhooks.Config.STRIPE_WEBHOOK_SECRET", "whsec_test"):
            with patch("api.webhooks.Config.STRIPE_SECRET_KEY", ""):
                with patch("stripe.Webhook.construct_event", return_value=event):
                    with patch("api.webhooks._is_captions_payment", return_value=False):
                        with patch("api.webhooks._is_captions_subscription_payment", return_value=True):
                            with patch("api.webhooks._handle_captions_payment", return_value=None):
                                with patch(
                                    "services.caption_order_service.CaptionOrderService",
                                    FakeOrderServiceNoRow,
                                ):
                                    with patch(
                                        "services.notifications.NotificationService.send_caption_checkout_webhook_missing_order_alert",
                                        return_value=True,
                                    ) as mock_alert:
                                        resp = client.post(
                                            "/webhooks/stripe",
                                            data=b"{}",
                                            headers={"Stripe-Signature": "t=1,v1=fake"},
                                        )

    assert resp.status_code == 500
    data = resp.get_json()
    assert data is not None
    assert data.get("error") == "caption order missing after captions checkout"
    mock_alert.assert_called_once()
    call_kw = mock_alert.call_args.kwargs
    assert call_kw.get("session_id") == session_id
    assert call_kw.get("reason") == "no_row_after_handle_captions_payment"
    assert call_kw.get("is_subscription_checkout") is True


def test_coerce_platform_selection_fills_defaults_deterministically():
    """When selected list is shorter than paid count, defaults are appended in stable order."""
    from api.webhooks import _coerce_platform_selection

    # Only one selected platform provided, but plan requires 4.
    out = _coerce_platform_selection("LinkedIn", 4)
    assert out == "LinkedIn, Instagram & Facebook, TikTok, Pinterest"

    # Legacy labels normalize and preserve expected order while filling.
    out2 = _coerce_platform_selection("Facebook, LinkedIn", 3)
    assert out2 == "Instagram & Facebook, LinkedIn, TikTok"


def test_merge_platform_list_preserves_explicit_pair_when_stripe_count_matches():
    """subscription.updated must not replace TikTok with LinkedIn when names already match Stripe count."""
    from api.billing_routes import merge_platform_list_with_stripe_count
    from api.webhooks import _coerce_platform_selection

    assert (
        merge_platform_list_with_stripe_count("Instagram & Facebook, TikTok", 2)
        == "Instagram & Facebook, TikTok"
    )
    # Incomplete list still uses default fill order (same as legacy _coerce_platform_selection).
    assert merge_platform_list_with_stripe_count("Instagram & Facebook", 2) == _coerce_platform_selection(
        "Instagram & Facebook", 2
    )
