#!/usr/bin/env python3
"""Regression: blank lines after labels are not treated as empty blocks."""

from services.caption_generator import _chunk_has_empty_blocks


def test_caption_and_hashtags_with_blank_lines_are_not_empty():
    content = """
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:**

Cap Ferrat Villas curates waterfront stays with private hosts and concierge planning before guests arrive.
Every stay includes tailored recommendations, smooth arrivals, and support throughout the week.

**Hashtags:**

#LuxuryVillas #FrenchRiviera #CapFerrat #VillaLife
""".strip()
    assert _chunk_has_empty_blocks(content, include_hashtags=True) is False

