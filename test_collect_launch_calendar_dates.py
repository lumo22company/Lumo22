#!/usr/bin/env python3
"""Tests for collect_launch_calendar_dates and OUT_OF_PACK prompt guard."""

import os

from datetime import date

os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")

from services.caption_generator import (
    collect_launch_calendar_dates,
    launch_window_start_for_intake_validation,
    _build_off_pack_window_dates_block,
    _build_user_prompt,
)


def test_collect_multi_event_april_range_and_literals():
    text = (
        "Early-bird registration closes 8 April. Main two-day summit 18-19 April. "
        "Thank-you / replay session 25 April."
    )
    dates = collect_launch_calendar_dates(text, "2026-04-16")
    assert dates == [
        date(2026, 4, 8),
        date(2026, 4, 18),
        date(2026, 4, 19),
        date(2026, 4, 25),
    ]


def test_out_of_pack_block_lists_before_day1():
    text = "Early-bird closes 8 April. Summit 18-19 April."
    block = _build_off_pack_window_dates_block("2026-04-16", text)
    assert "OUT_OF_PACK_CALENDAR" in block
    assert "Wed 08 Apr 2026" in block
    assert "already past" in block.lower()


def test_out_of_pack_empty_when_all_inside_window():
    text = "Summit 18-19 April."
    block = _build_off_pack_window_dates_block("2026-04-16", text)
    assert block == ""


def test_launch_window_start_uses_max_of_today_and_order_pack_start():
    """Stale order.pack_start in the past must not widen validation window backwards."""
    assert launch_window_start_for_intake_validation(date(2026, 4, 14), "2026-04-01") == "2026-04-14"
    assert launch_window_start_for_intake_validation(date(2026, 3, 10), "2026-04-01") == "2026-04-01"
    assert launch_window_start_for_intake_validation(date(2026, 4, 14), "") == "2026-04-14"


def test_user_prompt_includes_out_of_pack_when_early_date_before_pack():
    intake = {
        "business_name": "Riverside Events Co.",
        "business_type": "Events",
        "offer_one_line": "Corporate events on the riverfront",
        "audience": "Business leaders",
        "goal": "Registrations",
        "platform": "Instagram & Facebook",
        "caption_language": "English (UK)",
        "launch_event_description": (
            "Early-bird registration closes 8 April. Main two-day summit 18-19 April."
        ),
    }
    p = _build_user_prompt(intake, day_start=1, day_end=3, pack_start_date="2026-04-16")
    assert "OUT_OF_PACK_CALENDAR" in p
    assert "Wed 08 Apr 2026" in p
