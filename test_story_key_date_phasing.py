#!/usr/bin/env python3
"""
Regression test: stories must receive KEY_DATE_EVENTS and before/during/after phasing
when launch_event_description is set — same strategy as captions.

Prevents recurrence of bug where stories used wrong dates (e.g. "opens April" when launch was March 27).

Run: pytest test_story_key_date_phasing.py -v
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")


def test_stories_receive_key_date_phasing_when_launch_event_set():
    """When intake has launch_event_description, story prompt must include KEY_DATE_EVENTS and day phasing."""
    from unittest.mock import patch

    captured_prompts = []

    def fake_chat(system, user, temperature=0.6, max_tokens=4000):
        captured_prompts.append({"system": system, "user": user})
        return """
## 30 Story Ideas | Final | March 2026
**Day 1:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 2:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 3:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 4:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 5:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 6:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 7:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 8:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 9:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 10:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 11:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 12:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 13:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 14:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 15:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 16:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 17:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 18:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 19:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 20:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 21:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 22:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 23:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 24:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 25:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 26:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 27:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 28:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 29:** Idea: test. Suggested wording: test. Story hashtags: #test
**Day 30:** Idea: test. Suggested wording: test. Story hashtags: #test
"""

    intake = {
        "business_name": "Final",
        "offer_one_line": "Artisan chocolate",
        "audience": "Chocolate lovers",
        "goal": "Launch visibility",
        "platform": "Instagram & Facebook",
        "launch_event_description": "pop up shop launching on 27th March open for 2 weeks",
    }
    pack_start = "2026-03-21"  # Day 7 = Fri 27 Mar

    with patch("services.caption_generator.chat_completion", side_effect=fake_chat):
        from services.caption_generator import CaptionGenerator

        gen = CaptionGenerator()
        gen._generate_stories(intake, pack_start_date=pack_start)

    assert len(captured_prompts) >= 1, "Story generator should call chat_completion"
    user_prompt = captured_prompts[-1]["user"]

    # Must include key date events (same block as captions)
    assert "KEY_DATE_EVENTS" in user_prompt, "Story prompt must include KEY_DATE_EVENTS"
    assert "pop up shop" in user_prompt.lower() or "27" in user_prompt, "Launch description must be in prompt"

    # Must include before/during/after phasing (same strategy as captions)
    assert "BEFORE" in user_prompt and "AFTER" in user_prompt, "Must phase: BEFORE, ON/DURING, AFTER"
    assert "anticipation" in user_prompt.lower() or "teasers" in user_prompt.lower()
    assert "thank-you" in user_prompt.lower() or "thank you" in user_prompt.lower()

    # Must specify which day is launch day (Day 7 for 27 March when pack starts 21 March)
    assert "Day 7" in user_prompt, "Must tell AI key date falls on Day 7"
    low = user_prompt.lower()
    assert "pre-launch" in low or "pre-event" in low or "days 1 to 6" in user_prompt or "days **1**–**6**" in user_prompt
    assert "post-launch" in low or "post-event" in low or "days 8 to 30" in user_prompt or "days **8**–**30**" in user_prompt

    # Must warn against inventing wrong dates
    assert "do not invent" in user_prompt.lower() or "do not say" in user_prompt.lower()


def test_stories_without_launch_event_do_not_include_key_date_block():
    """When no launch_event_description, prompt should not force key-date phasing."""
    from unittest.mock import patch

    captured_prompts = []

    def fake_chat(system, user, temperature=0.6, max_tokens=4000):
        captured_prompts.append({"user": user})
        return "**Day 1:** Idea: x. Suggested wording: x. Story hashtags: #x\n" * 30

    intake = {
        "business_name": "Test",
        "offer_one_line": "Consulting",
        "audience": "Founders",
        "goal": "Leads",
        "platform": "Instagram & Facebook",
        "launch_event_description": "",  # No key date
    }

    with patch("services.caption_generator.chat_completion", side_effect=fake_chat):
        from services.caption_generator import CaptionGenerator

        gen = CaptionGenerator()
        gen._generate_stories(intake, pack_start_date="2026-03-21")

    user_prompt = captured_prompts[-1]["user"]
    # When launch_desc is empty, key_date_block is empty so KEY_DATE_EVENTS won't appear
    assert "KEY_DATE_EVENTS" not in user_prompt, "No key date block when launch_event_description is empty"
