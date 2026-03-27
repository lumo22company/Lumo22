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
        "stripe_checkout_session_id": session_id,
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

        def get_by_stripe_session_id(self, sid):
            return subscription_order if sid == session_id else None

        def get_by_token(self, token):
            return one_off_order if token == copy_from_token else None

        def save_intake(self, order_id, intake):
            FakeOrderService.last_saved = {"order_id": order_id, "intake": dict(intake)}
            return True

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
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


def test_coerce_platform_selection_fills_defaults_deterministically():
    """When selected list is shorter than paid count, defaults are appended in stable order."""
    from api.webhooks import _coerce_platform_selection

    # Only one selected platform provided, but plan requires 4.
    out = _coerce_platform_selection("LinkedIn", 4)
    assert out == "LinkedIn, Instagram & Facebook, TikTok, Pinterest"

    # Legacy labels normalize and preserve expected order while filling.
    out2 = _coerce_platform_selection("Facebook, LinkedIn", 3)
    assert out2 == "Instagram & Facebook, LinkedIn, TikTok"
