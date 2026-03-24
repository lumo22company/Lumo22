#!/usr/bin/env python3
"""Regression: generation delivery should not fail when building backup links."""

from unittest.mock import patch


def test_run_generation_and_deliver_uses_order_token_for_backup_links():
    import api.captions_routes as routes

    class FakeOrderService:
        def get_by_id(self, order_id):
            return {
                "id": order_id,
                "token": "tok-123",
                "status": "intake_completed",
                "customer_email": "user@example.com",
                "intake": {"platform": "Instagram & Facebook"},
                "stripe_subscription_id": "sub_123",
            }

        def set_generating(self, order_id):
            return True

        def set_delivered(self, order_id, captions_md, stories_pdf_bytes=None, captions_pdf_bytes=None):
            return True

        def append_pack_history(self, order_id, month_str, day_categories):
            return True

        def set_failed(self, order_id):
            return True

    class FakeGenerator:
        def generate(self, intake, previous_pack_themes=None, pack_start_date=None):
            return "## Day 1 - Authority\n**Platform:** Instagram & Facebook\n**Caption:** Hello world caption text long enough for tests.\n**Hashtags:** #a #b #c"

    class FakeNotif:
        def send_email_with_attachment(self, *args, **kwargs):
            return (True, None)

    with patch("services.caption_order_service.CaptionOrderService", FakeOrderService), \
         patch("services.caption_generator.CaptionGenerator", FakeGenerator), \
         patch("services.caption_generator.extract_day_categories_from_captions_md", return_value=["Authority"] * 30), \
         patch("services.caption_pdf.build_caption_pdf", return_value=b"%PDF-1.4"), \
         patch("services.caption_pdf.build_stories_pdf", return_value=None), \
         patch("services.caption_pdf.get_logo_path", return_value=""), \
         patch("services.notifications.NotificationService", FakeNotif), \
         patch("services.notifications._captions_delivery_email_html", return_value="<p>ok</p>"), \
         patch.object(routes.Config, "BASE_URL", "https://www.lumo22.com", create=True), \
         patch.object(routes.Config, "AI_PROVIDER", "openai", create=True):
        ok, err = routes._run_generation_and_deliver("ord-1")

    assert ok is True
    assert err is None
