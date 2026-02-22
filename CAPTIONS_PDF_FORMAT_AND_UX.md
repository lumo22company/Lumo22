# 30 Days Captions PDF — format, space-saving, and UX

## Reference format (what you asked for)

Your reference PDF uses:

1. **Cover page**
   - Title: **30 DAYS OF SOCIAL MEDIA CAPTIONS** (all caps)
   - Key–value lines: Business, Audience, Voice, Platform(s), Goal
   - Month year (e.g. FEBRUARY 2026)
   - **L U M O 2 2** (spaced, gold)

2. **Content**
   - **Day N — Category** as section headings
   - For each caption: small labels **Platform:**, **Suggested hook:**, **Hashtags** (if any), then the value/caption text
   - Compact vertical spacing

3. **Footer**
   - Page numbers: **— Page n —** (or “— 1 of 2 —” style if total is known)
   - Brand line: Lumo 22 · hello@lumo22.com

## What’s in the code

- **`services/caption_pdf.py`** has been updated to:
  - **Structured path:** Parse markdown into cover + days + caption blocks, then build:
    - Cover: 30 DAYS… (all caps), intake key–value lines, month year, L U M O 2 2
    - Content: Day headings + compact “label above value” blocks (Platform / Suggested hook / Hashtags + body)
    - Tighter spacing (e.g. 12 mm margins, 9 pt body, 10 pt day heading)
    - Page numbers via canvas callback: “— Page n —”
  - **Legacy path:** If the structured parser finds no days, it falls back to the previous block-based layout (still with brand colours and footer).

- Parser fixes applied:
  - Don’t break on the first “---” after INTAKE SUMMARY (so bullets are read).
  - Only break on “---” after at least one intake key (business, audience, voice, platform, goal) is set.
  - Use a dedicated `line_stripped` in the inner loop so the “## Day” break uses the current line, not the outer one.
  - Case-insensitive “day” checks and more tolerant Suggested hook / Platform matching.

If your delivery markdown matches the generator spec (## Day N — …, **Platform:** …, **Suggested hook:** …, body, **Hashtags:** …), the structured path should produce the reference-style PDF. If you still see the old layout, the markdown may differ slightly (e.g. extra blank lines or different label phrasing); the legacy path ensures a PDF is always generated.

## Space-saving and UX suggestions

- **Already in place**
  - Smaller margins (12 mm).
  - Smaller font sizes (e.g. 9 pt body, 10 pt day heading, 7 pt labels).
  - Tighter leading (e.g. 11 pt).
  - Cover on one page; no big logo on cover (optional logo can be re-added in a small size if you want).
  - Footer with Lumo 22 · hello@lumo22.com and page numbers.

- **Optional next steps**
  - **Two columns** for caption body text on large pages to save space (more complex in ReportLab).
  - **“Copy this caption”** hint or a clear visual block per caption to make copy-paste easier.
  - **Table of contents** (e.g. Day 1–30 with page numbers) if the document gets long.
  - **Total page count** in the footer (“— 1 of 12 —”) by doing a two-pass build (estimate or real count).

You can regenerate a sample with:

```bash
python3 scripts/generate_sample_captions_pdf.py
```

Then open `sample_30_days_captions.pdf` to confirm layout and spacing.
