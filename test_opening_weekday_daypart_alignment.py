"""Reject captions that open with the wrong weekday + morning/afternoon/evening vs DATE_CONTEXT."""
from datetime import date

from services.caption_generator import (
    _opening_weekday_daypart_alignment_error,
    _opening_weekday_daypart_wrong_calendar_day,
)


def test_opening_saturday_mornings_on_sunday_is_wrong():
    sunday = date(2026, 4, 19)
    cap = "Saturday mornings have a particular magic. The light comes in differently."
    assert _opening_weekday_daypart_wrong_calendar_day(cap, sunday) == "saturday"


def test_opening_sunday_mornings_on_sunday_ok():
    sunday = date(2026, 4, 19)
    cap = "Sunday mornings have a particular magic here."
    assert _opening_weekday_daypart_wrong_calendar_day(cap, sunday) is None


def test_alignment_error_finds_day7_mismatch():
    md = """
## Day 7 — Brand Personality

**Platform:** Instagram & Facebook

**Caption:**
Saturday mornings have a particular magic.

**Hashtags:** #Test
"""
    # Day 1 = Mon 13 Apr 2026 → Day 7 = Sun 19 Apr 2026
    err = _opening_weekday_daypart_alignment_error(md, "2026-04-13")
    assert err is not None
    assert "Day 7" in err
    assert "Sunday" in err
    assert "Saturday" in err


def test_alignment_passes_matching_weekday():
    md = """
## Day 7 — Brand Personality

**Platform:** Instagram & Facebook

**Caption:**
Sunday mornings are quiet here. Join us today.

**Hashtags:** #Test
"""
    assert _opening_weekday_daypart_alignment_error(md, "2026-04-13") is None
