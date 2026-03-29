#!/usr/bin/env python3
"""
Regression: caption_language from the intake form must drive all generation prompts consistently.

The PDFs render model output; this tests that the same intake key feeds captions + stories
(system prompt, user prompt, markdown header) so language cannot drift between paths.

Form options must match templates/captions_intake.html <select name="caption_language">.

Run: pytest test_caption_language_matches_intake.py -v
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")

# Must match option values in templates/captions_intake.html (caption_language select).
FORM_CAPTION_LANGUAGES = (
    "English (UK)",
    "English (US)",
    "Spanish",
    "French",
    "German",
    "Portuguese",
    "Italian",
    "Dutch",
    "Polish",
    "Turkish",
    "Swedish",
)


def _minimal_intake(lang: str) -> dict:
    return {
        "caption_language": lang,
        "business_name": "Test Biz",
        "business_type": "Service business",
        "offer_one_line": "We help clients.",
        "audience": "Small business owners",
        "goal": "Leads",
        "platform": "Instagram & Facebook",
    }


def test_form_options_match_language_instructions_dict():
    """Every form value must have a LANGUAGE_INSTRUCTIONS entry (no typos / drift)."""
    from services.caption_generator import LANGUAGE_INSTRUCTIONS

    for lang in FORM_CAPTION_LANGUAGES:
        assert lang in LANGUAGE_INSTRUCTIONS, f"Add LANGUAGE_INSTRUCTIONS[{lang!r}] or fix form"


def test_default_language_when_key_missing_is_english_uk():
    from services.caption_generator import LANGUAGE_INSTRUCTIONS, _build_system_prompt, _build_stories_system_prompt

    intake = {"business_name": "X", "audience": "Y", "platform": "Instagram & Facebook"}
    uk = LANGUAGE_INSTRUCTIONS["English (UK)"]
    assert uk in _build_system_prompt(intake)
    assert uk in _build_stories_system_prompt(intake, aligned_with_captions=False)


def test_stripped_whitespace_on_caption_language():
    from services.caption_generator import LANGUAGE_INSTRUCTIONS, _build_system_prompt

    fr = LANGUAGE_INSTRUCTIONS["French"]
    intake = _minimal_intake(" French ")
    assert fr in _build_system_prompt(intake)


def test_each_form_language_propagates_to_captions_stories_and_header():
    from services.caption_generator import (
        LANGUAGE_INSTRUCTIONS,
        _build_doc_header,
        _build_stories_system_prompt,
        _build_system_prompt,
        _build_user_prompt,
        _stories_language_user_block,
    )

    for lang in FORM_CAPTION_LANGUAGES:
        intake = _minimal_intake(lang)
        instruction = LANGUAGE_INSTRUCTIONS[lang]

        sys_captions = _build_system_prompt(intake)
        sys_stories = _build_stories_system_prompt(intake, aligned_with_captions=False)
        sys_stories_aligned = _build_stories_system_prompt(intake, aligned_with_captions=True)
        user = _build_user_prompt(
            intake, day_start=1, day_end=10, pack_start_date="2026-03-21"
        )
        header = _build_doc_header(intake, pack_start_date="2026-03-21")
        lock = _stories_language_user_block(lang)

        assert instruction in sys_captions, f"captions system missing instruction for {lang!r}"
        assert instruction in sys_stories, f"stories system missing instruction for {lang!r}"
        assert instruction in sys_stories_aligned, f"aligned stories system missing instruction for {lang!r}"

        assert f"- Caption language: {lang}" in user
        assert f"- Language: {lang}" in header

        assert f'The caption pack language is "{lang}"' in lock
        assert f'caption language is "{lang}"' in sys_stories


def test_french_intake_french_instructions_not_british_english():
    """Explicit check: French selection must not inject UK spelling rules into prompts."""
    from services.caption_generator import _build_system_prompt, _build_stories_system_prompt

    intake = _minimal_intake("French")
    sys_c = _build_system_prompt(intake)
    sys_s = _build_stories_system_prompt(intake, aligned_with_captions=False)

    assert "Write ALL captions and content in French" in sys_c
    assert "Write ALL captions and content in French" in sys_s
    assert "colour, favour" not in sys_c
    assert "colour, favour" not in sys_s
