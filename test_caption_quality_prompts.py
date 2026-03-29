#!/usr/bin/env python3
"""
Regression test: caption prompts must include full quality instructions for all intakes.

Ensures business relevance, key-date phasing, completeness, and quality bar are present
regardless of business type (consultancy, product, service).

Run: pytest test_caption_quality_prompts.py -v
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")


def _get_user_prompt(intake: dict, day_start: int = 1, day_end: int = 10) -> str:
    from services.caption_generator import _build_user_prompt
    return _build_user_prompt(intake, day_start=day_start, day_end=day_end, pack_start_date="2026-03-21")


def _get_system_prompt(intake: dict) -> str:
    from services.caption_generator import _build_system_prompt
    return _build_system_prompt(intake)


def test_consultancy_intake_gets_quality_instructions():
    """Consultancy intake must receive full quality prompt."""
    intake = {
        "business_name": "Strategy Co",
        "business_type": "Consultancy",
        "offer_one_line": "We help founders get clarity on strategy.",
        "audience": "Founders and small business owners",
        "goal": "More inquiries",
        "platform": "Instagram & Facebook, LinkedIn",
        "caption_language": "English (UK)",
    }
    sys_prompt = _get_system_prompt(intake)
    user_prompt = _get_user_prompt(intake)

    assert "Business relevance" in sys_prompt or "CRITICAL" in sys_prompt
    assert "Completeness" in sys_prompt
    assert "quality" in sys_prompt.lower() or "tailored" in sys_prompt.lower()
    assert "Strategy Co" in user_prompt or "strategy" in user_prompt.lower()


def test_product_brand_intake_gets_quality_instructions():
    """Product brand (e.g. chocolate) must receive full quality prompt."""
    intake = {
        "business_name": "Final",
        "business_type": "Product brand / E-commerce",
        "offer_one_line": "Artisan chocolate, single-origin cacao.",
        "audience": "Chocolate lovers, luxury gift buyers",
        "goal": "Launch visibility",
        "platform": "Instagram & Facebook",
        "launch_event_description": "Pop-up shop launching 27 March, open 2 weeks",
        "caption_language": "English (UK)",
    }
    sys_prompt = _get_system_prompt(intake)
    user_prompt = _get_user_prompt(intake)

    assert "Business relevance" in sys_prompt or "CRITICAL" in sys_prompt
    assert "KEY_DATE_EVENTS" in user_prompt
    assert "Day 7" in user_prompt
    assert "Final" in user_prompt
    assert "pre-launch" in user_prompt.lower() or "anticipation" in user_prompt.lower()
    assert "KEY_DATE_EVENTS — caption bodies" in user_prompt
    assert "**Caption:**" in user_prompt


def test_service_intake_without_key_date_gets_quality_instructions():
    """Service business without key date still gets full quality prompt."""
    intake = {
        "business_name": "Clean Home",
        "business_type": "Service business",
        "offer_one_line": "Eco-friendly cleaning for busy families.",
        "audience": "Parents, dual-income households",
        "goal": "Consistent presence",
        "platform": "Instagram & Facebook",
        "caption_language": "English (US)",
    }
    sys_prompt = _get_system_prompt(intake)
    user_prompt = _get_user_prompt(intake)

    assert "Business relevance" in sys_prompt or "CRITICAL" in sys_prompt
    # No launch-event intake block (DATE_CONTEXT may still mention KEY_DATE_EVENTS in guidance text)
    assert "KEY_DATE_EVENTS (user included dates in description):" not in user_prompt
    assert "Clean Home" in user_prompt or "cleaning" in user_prompt.lower()
    assert "DATE_ALIGNMENT" in user_prompt
    assert "DEADLINE_AND_REGISTRATION_ALIGNMENT" in user_prompt
    assert "as we head into the weekend" in user_prompt.lower()
    assert "Calendar-day alignment" in sys_prompt


def test_validate_caption_quality_flags_wrong_month():
    """Validation should flag launch-day content that references wrong month."""
    from services.caption_generator import _validate_caption_quality

    # Pack starts 21 Mar, Day 7 = 27 Mar. If Day 7 says "opens April" that's wrong.
    intake = {"launch_event_description": "pop-up 27 March"}
    captions_md = """
## Day 7 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** First line
Opens Saturday 4 April. Save the date.
---
"""
    warnings = _validate_caption_quality(captions_md, intake, "2026-03-21")
    assert len(warnings) >= 1
    assert "april" in warnings[0].lower() or "wrong month" in warnings[0].lower()


def test_validate_caption_quality_no_warning_when_dates_match():
    """Validation should not warn when launch-day content uses correct month."""
    from services.caption_generator import _validate_caption_quality

    intake = {"launch_event_description": "pop-up 27 March"}
    captions_md = """
## Day 7 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** First line
We're opening our pop-up this Saturday 27 March. Come visit.
---
"""
    warnings = _validate_caption_quality(captions_md, intake, "2026-03-21")
    assert len(warnings) == 0


def test_validate_deadline_vs_post_flags_closes_before_post_day():
    """Registration deadline before the post day (future tense) should warn."""
    from services.caption_generator import _validate_deadline_vs_post_dates

    # Day 1 = 29 Mar 2026 → Day 13 = Fri 10 Apr 2026 (same as user report pattern)
    captions_md = """
## Day 13 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** Early-bird registration closes on 8 April. The summit is Saturday 18 April.
---
"""
    w = _validate_deadline_vs_post_dates(captions_md, "2026-03-29")
    assert len(w) >= 1
    assert "Day 13" in w[0]


def test_validate_deadline_vs_post_silent_when_deadline_after_post_day():
    """Deadline after post day should not trigger deadline alignment warning."""
    from services.caption_generator import _validate_deadline_vs_post_dates

    captions_md = """
## Day 13 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** Early-bird registration closes on 12 April. Summit Saturday 18 April.
---
"""
    w = _validate_deadline_vs_post_dates(captions_md, "2026-03-29")
    assert len(w) == 0


def test_validate_deadline_vs_post_silent_past_tense():
    """Past tense (closed on) before post day should not warn."""
    from services.caption_generator import _validate_deadline_vs_post_dates

    captions_md = """
## Day 13 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** Early-bird registration closed on 8 April. General tickets still available.
---
"""
    w = _validate_deadline_vs_post_dates(captions_md, "2026-03-29")
    assert len(w) == 0
