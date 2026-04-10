"""Validation rejects impossible weekday + day + month phrases (e.g. Saturday 12 Apr when 12th is Sunday)."""

from services.caption_generator import (
    _invalid_weekday_dom_month_phrase,
    _explicit_weekday_dom_month_consistency_error,
)


def test_saturday_12_april_invalid_when_that_date_is_sunday():
    assert _invalid_weekday_dom_month_phrase(
        "Meridian Row Studio kiln opening: Saturday 12 April, 10am–5pm, Bristol.",
        2026,
    )


def test_saturday_11_april_valid():
    assert _invalid_weekday_dom_month_phrase(
        "Open Saturday 11 April from 10–5.",
        2026,
    ) is None


def test_full_markdown_fails_on_bad_phrase():
    md = """
## Day 2 — SOFT PROMOTION

**Platform:** Pinterest

**Caption:** Join us Saturday 12 April for the opening.

**Hashtags:** #test
"""
    err = _explicit_weekday_dom_month_consistency_error(md, "2026-04-10")
    assert err is not None
    assert "Day 2" in err
    assert "invalid calendar phrase" in err or "Saturday 12" in err
