# Caption Quality Standards

The bar for every caption set: **as tailored and specific as a premium copywriter would deliver** — regardless of business type, industry, or intake.

## Quality dimensions

| Dimension | Standard | How we enforce it |
|-----------|----------|-------------------|
| **Business relevance** | Every caption clearly about this business—their offer, audience, product. No generic "founder" or "strategy" copy. | System prompt: Business relevance (CRITICAL). Reader should know which industry and offer. |
| **Key date alignment** | When a launch/event date is given, captions and stories phase correctly: before = anticipation, on day = announce, after = thank-you. Dates in content match the actual calendar. | KEY_DATE_EVENTS + day mapping in prompt; stories receive same block. Post-gen validation flags date mismatches. |
| **Voice match** | Tone, style, and vocabulary match intake (voice_words, voice_avoid). No hype or buzzwords. | System prompt: tone rules, voice preferences override default. |
| **Variety** | No repetitive openers, phrases, or structures. Each caption feels distinct. | System prompt: anti-repetition, vary vocabulary and openings. |
| **Completeness** | Every day, every platform has a full caption (and hashtags when requested). No empty blocks or placeholders. | Retry on empty blocks; completeness rule in prompt. |
| **Platform fit** | LinkedIn vs TikTok vs Pinterest—each tailored. | Platform-specific rules in prompt. |
| **Date accuracy** | When key date is set (e.g. pop-up 27 March), content does not reference wrong dates (e.g. "opens April" on launch day). | Validation: `_validate_caption_quality()` checks launch-day content for wrong-month references. |
| **Brand name** | Real business name used correctly; no substitution with example/fictional names. | Brand rule in captions and stories prompts. |

## Reference: what "good" looks like

A strong caption set:

- Uses concrete, industry-specific language (not generic "founder" or "strategy")
- Phases key dates correctly: teasers before launch day, announcement on the day, thank-you after
- Keeps stories aligned with captions and the actual calendar
- Varies story types (BTS, poll, teaser, educational)
- References the correct dates from DATE_CONTEXT—never invents different ones (e.g. if launch is 27 March, no "opens in April" on launch day)

## Maintaining the bar

1. **Prompts:** Quality rules live in `services/caption_generator.py`. Do not weaken business relevance, phasing, or completeness rules.
2. **Regression tests:** `test_story_key_date_phasing.py` ensures stories get key-date phasing. `test_caption_quality_prompts.py` ensures diverse intakes get full quality instructions.
3. **Validation:** `_validate_caption_quality()` runs after generation and logs warnings for detectable issues (e.g. date mismatch). Review logs if quality slips.
4. **Periodic spot-checks:** When adding new features or changing prompts, generate with 2–3 diverse intakes (consultancy, product, service) and manually verify the output meets these standards.
