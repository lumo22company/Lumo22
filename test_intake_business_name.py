#!/usr/bin/env python3
"""Test that business_name flows through intake form → API → caption generator."""
import sys
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
    """When multiple platforms are in intake, user prompt must include rotation instruction."""
    import services.caption_generator as mod
    intake = {
        "business_name": "Test Co",
        "platform": "Instagram, LinkedIn",
        "offer_one_line": "Strategy for founders",
        "goal": "Leads",
    }
    prompt = mod._build_user_prompt(intake)
    assert "Assign each day" in prompt, "Multi-platform prompt should instruct to assign each day"
    assert "balanced rotation" in prompt, "Multi-platform prompt should mention balanced rotation"
    assert "**Platform:**" in prompt or "Platform:" in prompt, "Prompt should reference Platform label"
    assert "Instagram" in prompt and "LinkedIn" in prompt
    print("✓ Multi-platform prompt includes rotation instruction")


def test_single_platform_prompt_includes_rotation_instruction():
    """Single platform (e.g. LinkedIn) still gets rotation/label instruction so Platform: is clear."""
    import services.caption_generator as mod
    intake = {
        "business_name": "Test Co",
        "platform": "LinkedIn",
        "offer_one_line": "Strategy",
        "goal": "Leads",
    }
    prompt = mod._build_user_prompt(intake)
    assert "Assign each day" in prompt, "Single-platform prompt should still assign/label by day"
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


if __name__ == "__main__":
    test_caption_generator_prompt()
    test_caption_generator_no_business_name()
    test_intake_dict_structure()
    test_multi_platform_prompt_includes_rotation_instruction()
    test_single_platform_prompt_includes_rotation_instruction()
    test_no_platform_prompt_no_rotation_instruction()
    print("\nAll checks passed.")
