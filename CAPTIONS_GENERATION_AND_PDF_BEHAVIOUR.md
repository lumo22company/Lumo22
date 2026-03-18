# Captions generation and PDF behaviour

Short reference for how intake text is normalized and how incomplete AI output is handled.

## ALL CAPS normalization

If a user fills the intake form in ALL CAPS (e.g. business name **LAUNCH TEST**, voice **CASUAL**, key date **FREE CAKES FOR KIDS ON 30TH MARCH**), that text is **normalized** before it is sent to the AI and before it appears in the PDF. The PDF and captions are delivered in sentence/title case, not shouting.

- **Where it happens:** `services/caption_generator.py` — `_normalize_intake_case()`
- **When:** When building the user prompt (INTAKE section) and when building the doc header (PDF cover + intake summary).
- **Rules:**
  - If the string is mostly or fully uppercase (≥80% of letters are caps), it is converted.
  - **Title case** for short phrases: business name, audience, voice words, goal → e.g. `LAUNCH TEST` → "Launch Test", `CASUAL` → "Casual".
  - **Sentence case** for longer text: offer one line, audience cares, platform habits, key date description → e.g. `I MAKE CAKES` → "I make cakes", `FREE CAKES FOR KIDS ON 30TH MARCH` → "Free cakes for kids on 30th march."

So the AI receives and uses normalized text, and the PDF cover/intake summary never shows ALL CAPS from the form.

## Completeness and retry (no empty days/platforms)

Every day (1–30) must have a full caption (and hashtags when requested) for **every** platform. Empty **Caption:** or **Hashtags:** lines in the AI output are treated as incomplete.

- **System prompt:** Explicit instruction that every day and every platform must have non-empty Caption and Hashtags (when requested). No placeholders, no skipped days/platforms.
- **Chunk check:** After each chunk (days 1–10, 11–20, 21–30), the code checks for empty `**Caption:**` or `**Hashtags:**` lines (`_chunk_has_empty_blocks()` in `caption_generator.py`).
- **Retry:** If a chunk has empty blocks, that chunk is retried **once** with a stronger user message: "Your previous response had empty Caption or Hashtags lines. You must fill every **Caption:** and every **Hashtags:** (when requested) with real, copy-paste-ready content for every platform for every day in this range."
- **Failure:** If the retry still has empty blocks, generation raises `RuntimeError` so the job fails instead of delivering an incomplete PDF.

This reduces the chance of PDFs with missing entries (e.g. Day 11 or 12 with blank captions).

## Related

- **Key date → day number:** See prompt and `_parse_key_date_from_text()` — the key date from intake is parsed and the AI is told exactly which day number is "launch day" so phasing is correct.
- **PDF day headings with dates:** When `pack_start_date` is passed, each day in the PDF shows the real date (e.g. "Day 1 — Mon 18 Mar 2025 — Authority / Expertise").
- **Stories PDF Suggested wording:** Quotation marks around "Suggested wording" content are stripped in the PDF (`_strip_surrounding_quotes()` in `caption_pdf.py`), and the AI is instructed not to wrap that content in quotes.
