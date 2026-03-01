#!/usr/bin/env python3
"""
Test that "Add another platform" link appears only when editing intake (existing_intake set),
not when completing the form for the first time.
"""
from datetime import datetime, timezone
import sys

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


if __name__ == "__main__":
    test_intake_template()
    test_upgrade_required_response()
    print("All tests passed.")
