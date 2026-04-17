#!/usr/bin/env python3
"""When delivery_failure_count hits the cap, ops + customer notices are invoked."""

from unittest.mock import MagicMock, patch

from services.caption_delivery_recovery import CAPTIONS_MAX_AUTO_DELIVERY_FAILURES
from services.caption_order_service import CaptionOrderService


def test_record_delivery_failure_at_cap_calls_ops_and_customer_notice():
    oid = "order-uuid-1"
    row = {
        "delivery_failure_count": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES - 1,
        "customer_email": "customer@example.com",
        "token": "tok_abc",
        "intake": {"business_name": "Acme Co"},
        "stripe_subscription_id": "sub_x",
        "stripe_customer_id": "cus_y",
    }
    svc = CaptionOrderService.__new__(CaptionOrderService)
    svc.get_by_id = MagicMock(return_value=row)
    svc.update = MagicMock(return_value=True)

    ops = MagicMock(return_value=True)
    cust = MagicMock(return_value=True)
    with patch("services.notifications.NotificationService") as NS:
        inst = MagicMock()
        inst.send_caption_delivery_retries_exhausted_alert = ops
        inst.send_caption_delivery_retries_exhausted_customer_notice = cust
        NS.return_value = inst

        ok = CaptionOrderService.record_delivery_failure(svc, oid, "send failed")

    assert ok is True
    svc.update.assert_called_once()
    ops.assert_called_once()
    cust.assert_called_once_with("customer@example.com", business_name="Acme Co")


def test_record_delivery_failure_below_cap_does_not_notify():
    oid = "order-uuid-2"
    row = {
        "delivery_failure_count": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES - 2,
        "customer_email": "customer@example.com",
        "token": "",
        "intake": {},
    }
    svc = CaptionOrderService.__new__(CaptionOrderService)
    svc.get_by_id = MagicMock(return_value=row)
    svc.update = MagicMock(return_value=True)

    with patch("services.notifications.NotificationService") as NS:
        inst = MagicMock()
        NS.return_value = inst
        ok = CaptionOrderService.record_delivery_failure(svc, oid, "err")

    assert ok is True
    inst.send_caption_delivery_retries_exhausted_alert.assert_not_called()
    inst.send_caption_delivery_retries_exhausted_customer_notice.assert_not_called()


def test_record_delivery_failure_at_cap_skips_customer_without_email():
    oid = "order-uuid-3"
    row = {
        "delivery_failure_count": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES - 1,
        "customer_email": "",
        "token": "",
        "intake": {},
    }
    svc = CaptionOrderService.__new__(CaptionOrderService)
    svc.get_by_id = MagicMock(return_value=row)
    svc.update = MagicMock(return_value=True)

    ops = MagicMock(return_value=True)
    cust = MagicMock(return_value=True)
    with patch("services.notifications.NotificationService") as NS:
        inst = MagicMock()
        inst.send_caption_delivery_retries_exhausted_alert = ops
        inst.send_caption_delivery_retries_exhausted_customer_notice = cust
        NS.return_value = inst

        ok = CaptionOrderService.record_delivery_failure(svc, oid, "err")

    assert ok is True
    ops.assert_called_once()
    cust.assert_not_called()
