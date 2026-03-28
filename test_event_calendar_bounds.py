#!/usr/bin/env python3
"""Tests for event date range parsing, weekend phrasing rules, and quality warnings."""
from datetime import date


def test_parse_event_range_same_month():
    from services.caption_generator import _parse_event_range_dates

    start = "2026-03-28"
    raw = "Spring rare-drop preview 12-13 April (online)"
    r = _parse_event_range_dates(raw, start)
    assert r == (date(2026, 4, 12), date(2026, 4, 13))


def test_resolve_bounds_maps_pack_days():
    from services.caption_generator import _resolve_event_pack_bounds

    b = _resolve_event_pack_bounds("2026-03-28", "12–13 April online")
    assert b is not None
    da, db, sd, ed = b
    assert da == date(2026, 4, 12)
    assert db == date(2026, 4, 13)
    assert sd == 16 and ed == 17


def test_event_calendar_allows_weekend_phrase_sat_sun_only():
    from services.caption_generator import _event_calendar_allows_weekend_phrase

    assert _event_calendar_allows_weekend_phrase(date(2026, 4, 11), date(2026, 4, 12))
    assert not _event_calendar_allows_weekend_phrase(date(2026, 4, 12), date(2026, 4, 13))
    assert _event_calendar_allows_weekend_phrase(date(2026, 4, 12), date(2026, 4, 12))


def test_strict_block_includes_weekend_wording_and_weekday_lock():
    from services.caption_generator import _build_event_calendar_strict_block

    block = _build_event_calendar_strict_block("2026-03-28", "12-13 April")
    assert block is not None
    assert "WEEKDAY_LOCK" in block
    assert "WEEKEND_WORDING" in block
    assert "Sunday" in block and "Monday" in block
    assert "Saturday and Sunday" in block or "not" in block.lower()


def test_validate_caption_quality_weekend_warning_sun_mon():
    from services.caption_generator import _validate_caption_quality

    intake = {"launch_event_description": "preview 12-13 April"}
    md = "This weekend only. Next weekend we open. " + "x" * 200
    w = _validate_caption_quality(md, intake, "2026-03-28")
    assert any("weekend" in x.lower() and "EVENT_CALENDAR" in x for x in w)


def test_validate_caption_quality_no_weekend_warning_when_sat_sun_event():
    from services.caption_generator import _validate_caption_quality

    intake = {"launch_event_description": "drop 11-12 April"}
    md = "Next weekend we open. " + "x" * 200
    w = _validate_caption_quality(md, intake, "2026-04-06")
    assert not any("EVENT_CALENDAR" in x for x in w)


def test_build_key_date_events_story_block_contains_event_calendar():
    from services.caption_generator import _build_key_date_events_story_block

    n = _build_key_date_events_story_block(
        "2026-03-28",
        "12-13 April",
        "preview 12-13 April",
    )
    assert "KEY_DATE_EVENTS" in n
    assert "EVENT_CALENDAR" in n


def test_build_user_prompt_includes_strict_block_for_range():
    from services.caption_generator import _build_user_prompt

    intake = {
        "business_name": "Test",
        "business_type": "Shop",
        "offer_one_line": "Plants",
        "audience": "Collectors",
        "audience_cares": "Quality",
        "voice_words": "warm",
        "voice_avoid": "",
        "platform": "Instagram",
        "platform_habits": "Stories",
        "goal": "Sales",
        "launch_event_description": "Rare drop 12-13 April",
    }
    p = _build_user_prompt(intake, pack_start_date="2026-03-28")
    assert "EVENT_CALENDAR" in p
    assert "Pack Days **16**–**17**" in p or "16**–**17" in p.replace(" ", "")
