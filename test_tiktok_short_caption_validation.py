#!/usr/bin/env python3
"""Regression: TikTok captions can be short without failing structure validation."""

from services.caption_generator import _chunk_structure_error


def test_tiktok_short_caption_is_allowed():
    content = """
## Day 1 — AUTHORITY
**Platform:** TikTok
**Caption:** Three quick hooks.
Act now.
Save this.
**Hashtags:** #growth #smallbusiness #content
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["TikTok"],
        include_hashtags=True,
        hashtag_min=1,
        hashtag_max=10,
    )
    assert err is None
