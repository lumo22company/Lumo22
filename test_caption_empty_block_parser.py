#!/usr/bin/env python3

from services.caption_generator import _chunk_has_empty_blocks


def test_caption_block_with_blank_line_is_not_empty():
    content = """
## Day 1 — AUTHORITY / EXPERTISE
**Platform:** Instagram & Facebook
**Caption:**

This is a full caption paragraph with real content.

**Hashtags:** #one #two #three
---
""".strip()
    assert _chunk_has_empty_blocks(content, include_hashtags=True) is False


def test_truly_empty_caption_block_is_empty():
    content = """
## Day 1 — AUTHORITY / EXPERTISE
**Platform:** Instagram & Facebook
**Caption:**
**Hashtags:** #one #two #three
---
""".strip()
    assert _chunk_has_empty_blocks(content, include_hashtags=True) is True
