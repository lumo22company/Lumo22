"""Tests for stripping duplicate dates from day themes before PDF headers."""
from services.caption_pdf import _strip_redundant_date_from_theme


def test_strip_double_date_prefix_matches_pack_day():
    # Day 11 of pack starting 2026-03-27 is 2026-04-05 (0-index: day 1 = Mar 27)
    # Mar has 31 days: 27->1, 28->2, 29->3, 30->4, 31->5, Apr 1->6, ... Apr 5->11
    theme = "Mon 06 Apr 2026 — Monday 06 Apr 2026 — Educational / Value"
    out = _strip_redundant_date_from_theme(theme, "2026-03-27", 11)
    assert out == "Educational / Value"


def test_strip_single_date_prefix():
    theme = "Tue 15 Apr 2026 — Brand Personality"
    out = _strip_redundant_date_from_theme(theme, "2026-04-01", 15)
    assert out == "Brand Personality"


def test_does_not_strip_when_date_differs():
    theme = "Mon 01 Apr 2026 — Wrong day"
    out = _strip_redundant_date_from_theme(theme, "2026-04-01", 15)
    assert out == theme


def test_no_pack_date_leaves_theme_unchanged():
    t = "Mon 06 Apr 2026 — Educational / Value"
    assert _strip_redundant_date_from_theme(t, None, 11) == t
