#!/usr/bin/env python3
"""
Regression test: story prompts must include full quality instructions for all intakes.

Ensures business relevance, key-date phasing, quality bar, and completeness rules
are present regardless of business type (consultancy, product, service).

Run: pytest test_story_quality_prompts.py -v
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")


def test_consultancy_story_prompt_gets_quality_instructions():
    """Consultancy intake must receive full quality story prompt."""
    from unittest.mock import patch
    captured = []

    def capture_prompt(system, user, **kw):
        captured.append({"system": system, "user": user})
        return "\n".join(f"**Day {i}:** Idea: x. Suggested wording: x. Story hashtags: #a #b" for i in range(1, 31))

    intake = {
        "business_name": "Strategy Co",
        "offer_one_line": "We help founders get clarity.",
        "audience": "Founders",
        "goal": "More inquiries",
        "platform": "Instagram & Facebook",
        "include_stories": True,
    }
    with patch("services.caption_generator.chat_completion", side_effect=capture_prompt):
        from services.caption_generator import CaptionGenerator
        gen = CaptionGenerator()
        gen._generate_stories(intake, pack_start_date="2026-03-21")

    assert len(captured) >= 1
    user = captured[-1]["user"]
    assert "Strategy Co" in user or "strategy" in user.lower()
    assert "quality" in user.lower() or "tailored" in user.lower()
    assert "Idea:" in user and "Suggested wording:" in user and "Story hashtags:" in user


def test_product_brand_with_key_date_story_prompt_gets_phasing():
    """Product brand with key date must get KEY_DATE_EVENTS and day phasing."""
    from unittest.mock import patch
    captured = []

    def capture_prompt(system, user, **kw):
        captured.append({"user": user})
        return "\n".join(f"**Day {i}:** Idea: x. Suggested wording: x. Story hashtags: #a #b" for i in range(1, 31))

    intake = {
        "business_name": "Final",
        "offer_one_line": "Artisan chocolate",
        "audience": "Chocolate lovers",
        "goal": "Launch visibility",
        "platform": "Instagram & Facebook",
        "launch_event_description": "pop-up 27 March, open 2 weeks",
    }
    with patch("services.caption_generator.chat_completion", side_effect=capture_prompt):
        from services.caption_generator import CaptionGenerator
        gen = CaptionGenerator()
        gen._generate_stories(intake, pack_start_date="2026-03-21")

    user = captured[-1]["user"]
    assert "KEY_DATE_EVENTS" in user
    assert "Day 7" in user
    assert "Final" in user
    assert "pre-launch" in user.lower() or "anticipation" in user.lower()


def test_validate_story_quality_flags_missing_days():
    """Validation should flag when story output is missing days."""
    from services.caption_generator import _validate_story_quality

    stories_md = "\n".join(f"**Day {i}:** Idea: x. Suggested wording: x. Story hashtags: #a #b" for i in [1, 2, 3])
    warnings = _validate_story_quality(stories_md)
    assert len(warnings) >= 1
    assert "missing days" in warnings[0].lower()


def test_validate_story_quality_flags_empty_parts():
    """Validation should flag when a day has no Idea/Suggested wording."""
    from services.caption_generator import _validate_story_quality

    stories_md = "**Day 1:** Idea: test. Suggested wording: test. Story hashtags: #a #b\n**Day 2:** \n**Day 3:** Idea only."
    warnings = _validate_story_quality(stories_md)
    assert any("missing" in w.lower() or "no content" in w.lower() for w in warnings)


def test_validate_story_quality_no_warning_when_complete():
    """Validation should not warn when all 30 days have required parts."""
    from services.caption_generator import _validate_story_quality

    stories_md = "\n".join(
        f"**Day {i}:** Idea: idea. Suggested wording: words. Story hashtags: #a #b #c" for i in range(1, 31)
    )
    warnings = _validate_story_quality(stories_md)
    assert len(warnings) == 0
