#!/usr/bin/env python3
"""Regression: stories generation failure should still deliver captions."""

from unittest.mock import patch


def test_run_generation_and_deliver_falls_back_to_captions_only_when_stories_fail():
    import api.captions_routes as routes

    calls = {"updates": []}

    class FakeOrderService:
        def get_by_id(self, order_id):
            return {
                "id": order_id,
                "token": "tok-456",
                "status": "intake_completed",
                "customer_email": "user@example.com",
                "intake": {"platform": "Instagram & Facebook", "include_stories": True, "align_stories_to_captions": True},
                "stripe_subscription_id": "",
            }

        def set_generating(self, order_id):
            return True

        def update(self, order_id, updates):
            calls["updates"].append(updates)
            return True

        def set_delivered(self, order_id, captions_md, stories_pdf_bytes=None, captions_pdf_bytes=None):
            return True

        def append_pack_history(self, order_id, month_str, day_categories):
            return True

        def record_delivery_failure(self, order_id, message):
            calls["updates"].append({"failure": message})
            return True

        def set_failed(self, order_id):
            return True

    class FakeGenerator:
        def generate(self, intake, previous_pack_themes=None, pack_start_date=None):
            if intake.get("include_stories"):
                raise RuntimeError(
                    "Stories output invalid after retry (initial: Stories output is empty or missing day entries; retry: Stories output is empty or missing day entries)"
                )
            return "## Day 1 — AUTHORITY / EXPERTISE\n**Platform:** Instagram & Facebook\n**Caption:** A complete fallback caption with enough detail.\n**Hashtags:** #one #two #three"

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
        ok, err = routes._run_generation_and_deliver("ord-fallback")

    assert ok is True
    assert err is None
    assert any(u.get("stories_generation_status") == "failed" for u in calls["updates"] if isinstance(u, dict))
