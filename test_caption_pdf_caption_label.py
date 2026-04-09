"""PDF table layout must label the caption row Caption:, not Suggested hook: (markdown may still use Suggested hook)."""

from io import BytesIO

from pypdf import PdfReader

from services.caption_pdf import build_caption_pdf


def test_pdf_uses_caption_label_not_suggested_hook():
    md = """# 30 Days of Social Media Captions

**Business:** Test Co
**Audience:** Founders
**Voice:** Direct
**Platform(s):** LinkedIn
**Goal:** Leads

## Day 1 — Authority

**Platform:** LinkedIn

**Suggested hook:** First line of the post for day one.

**Hashtags:** #test #day1

---
"""
    pdf_bytes = build_caption_pdf(md, logo_path=None, pack_start_date="2026-03-01")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""

    assert "Caption:" in text
    assert "Suggested hook:" not in text
    assert "Suggested Hook:" not in text
