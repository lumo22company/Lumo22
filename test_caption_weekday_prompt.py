"""Caption prompt includes weekday/hook alignment when DATE_CONTEXT is present."""

from services.caption_generator import _build_user_prompt, _build_weekday_hook_alignment_block


def test_weekday_hook_alignment_block_content():
    b = _build_weekday_hook_alignment_block()
    assert "WEEKDAY_IN_HOOK_ALIGNMENT" in b
    assert "DATE_CONTEXT" in b
    assert "Monday mornings" in b or "Wednesday" in b


def test_build_user_prompt_includes_weekday_alignment():
    p = _build_user_prompt(
        {"business_name": "Test Studio", "audience": "women"},
        pack_start_date="2026-04-03",
    )
    assert "WEEKDAY_IN_HOOK_ALIGNMENT" in p
    assert "Day 13 = Wed 15 Apr 2026" in p or "Day 1 = Fri 03 Apr 2026" in p
