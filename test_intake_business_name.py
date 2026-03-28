#!/usr/bin/env python3
"""Test that business_name flows through intake form → API → caption generator."""
import sys
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv
load_dotenv()


def test_caption_generator_prompt():
    """Verify _build_user_prompt includes business_name."""
    from services.caption_generator import CaptionGenerator
    # Access the module's _build_user_prompt directly
    import services.caption_generator as mod
    intake = {
        "business_name": "Acme Coaching",
        "business_type": "Consultancy",
        "offer_one_line": "Strategy for founders",
        "audience": "Founders",
        "audience_cares": "Clarity",
        "voice_words": "direct, calm",
        "voice_avoid": "hype",
        "platform": "LinkedIn",
        "platform_habits": "short posts",
        "goal": "Leads",
        "include_hashtags": True,
        "hashtag_min": 3,
        "hashtag_max": 10,
    }
    prompt = mod._build_user_prompt(intake)
    assert "Acme Coaching" in prompt, f"business_name should appear in prompt, got: {prompt[:500]}"
    assert "- Business name: Acme Coaching" in prompt
    print("✓ Caption generator includes business_name in prompt")


def test_caption_generator_no_business_name():
    """Verify prompt handles missing business_name."""
    import services.caption_generator as mod
    intake = {
        "business_type": "Consultancy",
        "offer_one_line": "Strategy",
    }
    prompt = mod._build_user_prompt(intake)
    assert "Not specified" in prompt or "business name" in prompt.lower()
    print("✓ Caption generator handles missing business_name")


def test_intake_dict_structure():
    """Verify API-style intake dict includes business_name (no HTTP)."""
    data = {
        "business_name": "Test Co",
        "business_type": "Agency",
        "offer_one_line": "Marketing",
    }
    intake = {
        "business_name": (data.get("business_name") or "").strip(),
        "business_type": (data.get("business_type") or "").strip(),
        "offer_one_line": (data.get("offer_one_line") or "").strip(),
    }
    assert intake.get("business_name") == "Test Co"
    print("✓ Intake dict structure includes business_name")


def test_multi_platform_prompt_includes_rotation_instruction():
    """When multiple platforms are in intake, user prompt must instruct one caption per platform per day."""
    import services.caption_generator as mod
    intake = {
        "business_name": "Test Co",
        "platform": "Instagram, LinkedIn",
        "offer_one_line": "Strategy for founders",
        "goal": "Leads",
    }
    prompt = mod._build_user_prompt(intake)
    assert "EACH day" in prompt or "each day" in prompt, "Multi-platform prompt should reference each day"
    assert "EACH of these platforms" in prompt or "one caption for EACH" in prompt, "Multi-platform prompt should require one caption per platform per day"
    assert "**Platform:**" in prompt or "Platform:" in prompt, "Prompt should reference Platform label"
    assert "Instagram" in prompt and "LinkedIn" in prompt
    print("✓ Multi-platform prompt includes rotation instruction")


def test_single_platform_prompt_includes_rotation_instruction():
    """Single platform (e.g. LinkedIn) gets per-day and Platform label instruction."""
    import services.caption_generator as mod
    intake = {
        "business_name": "Test Co",
        "platform": "LinkedIn",
        "offer_one_line": "Strategy",
        "goal": "Leads",
    }
    prompt = mod._build_user_prompt(intake)
    assert "one caption per day" in prompt or "per day" in prompt, "Single-platform prompt should instruct one caption per day"
    assert "**Platform:**" in prompt or "Platform:" in prompt, "Single-platform prompt should label with Platform"
    assert "LinkedIn" in prompt
    print("✓ Single-platform prompt includes rotation/label instruction")


def test_no_platform_prompt_no_rotation_instruction():
    """When platform is missing or 'Not specified', rotation instruction is not added."""
    import services.caption_generator as mod
    intake = {
        "business_name": "Test Co",
        "offer_one_line": "Strategy",
        "goal": "Leads",
    }
    prompt = mod._build_user_prompt(intake)
    assert "Assign each day (1–30) to one of the platforms above in a balanced rotation" not in prompt
    print("✓ No platform: rotation instruction not added")


def test_enrich_intake_from_checkout_session_seeds_when_webhook_late():
    """If DB intake has no business_name yet, enrich loads Stripe session metadata and seeds."""
    from unittest.mock import MagicMock, patch
    from api.captions_routes import enrich_order_intake_from_checkout_session

    mock_svc = MagicMock()
    order = {"id": "ord-1", "stripe_session_id": "cs_test_abc", "intake": {}}
    fake_session = {"metadata": {"business_name": "Stripe Early Ltd"}}
    updated = {"id": "ord-1", "stripe_session_id": "cs_test_abc", "intake": {"business_name": "Stripe Early Ltd"}}
    mock_svc.get_by_id.return_value = updated

    with patch("stripe.checkout.Session.retrieve", return_value=fake_session):
        with patch("api.captions_routes.Config") as cfg:
            cfg.STRIPE_SECRET_KEY = "sk_test_fake"
            out = enrich_order_intake_from_checkout_session(mock_svc, order)

    assert mock_svc.update_intake_only.called
    call_intake = mock_svc.update_intake_only.call_args[0][1]
    assert call_intake.get("business_name") == "Stripe Early Ltd"
    assert out.get("intake", {}).get("business_name") == "Stripe Early Ltd"
    print("✓ enrich_order_intake_from_checkout_session seeds from Stripe when intake empty")


def test_enrich_intake_skips_when_name_already_set():
    from unittest.mock import MagicMock, patch
    from api.captions_routes import enrich_order_intake_from_checkout_session

    mock_svc = MagicMock()
    order = {"id": "ord-1", "stripe_session_id": "cs_x", "intake": {"business_name": "Already Here"}}
    with patch("stripe.checkout.Session.retrieve") as mock_retrieve:
        out = enrich_order_intake_from_checkout_session(mock_svc, order)
    mock_retrieve.assert_not_called()
    assert out == order
    print("✓ enrich skips Stripe when business_name already in intake")


def test_oneoff_checkout_puts_business_name_in_stripe_metadata():
    """Optional pre-checkout business name is passed to Stripe metadata for webhook → intake seeding."""
    from app import app

    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    with app.test_client() as client:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = fake_session
            with patch("api.captions_routes._get_referral_coupon_id") as mock_coupon:
                mock_coupon.return_value = None
                r = client.get("/api/captions-checkout?platforms=1&business_name=Acme%20Bakery")
    assert r.status_code == 302, r.status_code
    md = mock_create.call_args[1]["metadata"]
    assert md.get("business_name") == "Acme Bakery"
    assert md.get("business_key") == "acme-bakery"
    print("✓ One-off checkout includes business_name in Stripe metadata")


if __name__ == "__main__":
    test_caption_generator_prompt()
    test_caption_generator_no_business_name()
    test_intake_dict_structure()
    test_multi_platform_prompt_includes_rotation_instruction()
    test_single_platform_prompt_includes_rotation_instruction()
    test_no_platform_prompt_no_rotation_instruction()
    test_enrich_intake_from_checkout_session_seeds_when_webhook_late()
    test_enrich_intake_skips_when_name_already_set()
    test_oneoff_checkout_puts_business_name_in_stripe_metadata()
    print("\nAll checks passed.")
