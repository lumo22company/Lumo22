#!/usr/bin/env python3
"""
Test that "Add another platform" link appears only when editing intake (existing_intake set),
not when completing the form for the first time.
"""
from datetime import datetime, timezone
import sys
from unittest.mock import MagicMock, patch

def test_intake_template():
    from app import app
    now = datetime.now(timezone.utc)
    with app.test_request_context():
        from flask import render_template

        # First-time completion: no existing intake
        html_first = render_template(
            "captions_intake.html",
            intake_token="test-token-123",
            existing_intake={},
            intake_returning_editor=False,
            intake_view_only=False,
            account_upgrade_base_url="",
            platforms_count=1,
            prefilled_platform="",
            stories_paid=False,
            now=now,
        )
        has_add_platform_first = "Add another platform" in html_first

        # Editing: existing intake present
        html_edit = render_template(
            "captions_intake.html",
            intake_token="test-token-123",
            existing_intake={"business_name": "Test Co", "platform": "LinkedIn"},
            intake_returning_editor=True,
            intake_view_only=False,
            account_upgrade_base_url="",
            platforms_count=1,
            prefilled_platform="LinkedIn",
            stories_paid=False,
            now=now,
        )
        has_add_platform_edit = "Add another platform" in html_edit

        if has_add_platform_first:
            print("FAIL: First-time intake should NOT show 'Add another platform'")
            sys.exit(1)
        if not has_add_platform_edit:
            print("FAIL: Edit intake should show 'Add another platform'")
            sys.exit(1)
        print("PASS: 'Add another platform' only visible when editing (existing_intake set)")


def test_awaiting_intake_with_seeded_business_shows_next_step():
    """Stripe/checkout often seeds only business_name; button must not say REVIEW CHANGES."""
    from app import app

    mock_order = {
        "id": "ord-1",
        "token": "tok-seed",
        "status": "awaiting_intake",
        "intake": {"business_name": "From Checkout"},
        "platforms_count": 1,
        "selected_platforms": "",
        "include_stories": False,
        "customer_email": "buyer@example.com",
        "stripe_subscription_id": "",
        "upgraded_from_token": "",
    }
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_by_token.return_value = dict(mock_order)
            MockSvc.return_value = mock_svc
            with patch(
                "api.captions_routes.enrich_order_intake_from_checkout_session",
                lambda svc, o: o,
            ):
                r = client.get("/captions-intake?t=tok-seed")
    if r.status_code != 200:
        print(f"FAIL: expected 200, got {r.status_code}")
        sys.exit(1)
    html = r.get_data(as_text=True)
    if "NEXT STEP" not in html or "REVIEW CHANGES" in html:
        print("FAIL: First-time awaiting_intake should show NEXT STEP, not REVIEW CHANGES")
        sys.exit(1)
    print("PASS: Seeded awaiting_intake shows NEXT STEP")


def test_upgrade_required_response():
    """Check API returns upgrade_required when form requests Stories but order does not include it."""
    from app import app
    from unittest.mock import patch, MagicMock

    # Simulate an order with no Stories add-on
    mock_order = {
        "id": "ord-123",
        "token": "test-tok",
        "status": "intake_completed",
        "platforms_count": 1,
        "include_stories": False,
        "intake": {"business_name": "Test"},
        "customer_email": "test@example.com",
    }
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_by_token.return_value = mock_order
            MockSvc.return_value = mock_svc

            r = client.post(
                "/api/captions-intake",
                json={
                    "token": "test-tok",
                    "t": "test-tok",
                    "business_name": "Test Co",
                    "include_stories": True,
                },
                content_type="application/json",
            )
    data = r.get_json() or {}
    if r.status_code != 400 or not data.get("upgrade_required") or data.get("upgrade_type") != "stories":
        print("FAIL: API should return 400 with upgrade_required for Stories when order has no Stories")
        sys.exit(1)
    print("PASS: API returns upgrade_required when form requests Stories but order does not include it")


def test_oneoff_edit_blocked_after_completed():
    """One-off orders cannot POST intake updates after first submit; subscription edits still allowed."""
    from app import app
    from unittest.mock import patch, MagicMock

    one_off = {
        "id": "ord-oneoff",
        "token": "tok-oneoff",
        "status": "delivered",
        "platforms_count": 1,
        "include_stories": False,
        "intake": {"business_name": "Old", "platform": "LinkedIn", "goal": "Build authority"},
        "customer_email": "a@example.com",
        "stripe_subscription_id": "",
    }
    sub_order = {
        **one_off,
        "id": "ord-sub",
        "token": "tok-sub",
        "stripe_subscription_id": "sub_123",
    }
    payload = {
        "token": "tok-oneoff",
        "business_name": "New Name",
        "business_type": "Agency",
        "offer_one_line": "We help teams",
        "audience": "Founders",
        "audience_cares": "Growth",
        "platform": "LinkedIn",
        "goal": "Build authority",
    }
    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_by_token.return_value = dict(one_off)
            mock_svc.has_subscription_upgraded_from_oneoff_token.return_value = False
            MockSvc.return_value = mock_svc
            r = client.post("/api/captions-intake", json=payload, content_type="application/json")
    data = r.get_json() or {}
    if r.status_code != 400 or not data.get("oneoff_edit_blocked"):
        print("FAIL: one-off edit after delivered should return 400 with oneoff_edit_blocked")
        sys.exit(1)
    if "upgrade_account_url" not in data or "account/upgrade" not in (data.get("upgrade_account_url") or ""):
        print("FAIL: response should include upgrade_account_url")
        sys.exit(1)
    assert mock_svc.update_intake_only.call_count == 0

    with app.test_client() as client:
        with patch("services.caption_order_service.CaptionOrderService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_by_token.return_value = dict(sub_order)
            mock_svc.has_subscription_upgraded_from_oneoff_token.return_value = False
            mock_svc.update_intake_only.return_value = True
            MockSvc.return_value = mock_svc
            r2 = client.post(
                "/api/captions-intake",
                json={**payload, "token": "tok-sub"},
                content_type="application/json",
            )
    d2 = r2.get_json() or {}
    if r2.status_code != 200 or not d2.get("success"):
        print("FAIL: subscription order should still allow intake edit", r2.status_code, d2)
        sys.exit(1)
    print("PASS: One-off edit blocked; subscription edit allowed")


if __name__ == "__main__":
    test_intake_template()
    test_awaiting_intake_with_seeded_business_shows_next_step()
    test_upgrade_required_response()
    test_oneoff_edit_blocked_after_completed()
    print("All tests passed.")
