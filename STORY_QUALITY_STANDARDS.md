# Story Idea PDF Quality Standards

The bar for every story idea set: **as tailored and specific as a premium content strategist would deliver** — regardless of business type, industry, or intake.

## Quality dimensions

| Dimension | Standard | How we enforce it |
|-----------|----------|-------------------|
| **Key date alignment** | When a launch/event date is given, stories phase correctly: before = anticipation/teasers, on day = announce, after = thank-you. Suggested wording uses the actual dates from DATE_CONTEXT—no invented dates. | KEY_DATE_EVENTS + day mapping in both _generate_stories and _generate_stories_aligned. Post-gen validation flags date mismatches. |
| **Business relevance** | Every Idea and Suggested wording clearly about this business—their offer, audience, product. No generic industry examples. | Brand rule in prompt; intake (offer, audience, goal) passed through. |
| **Brand name** | Real business name used correctly in Idea/Suggested wording; no substitution with example or fictional names. | CRITICAL brand rule in both story prompts. |
| **Variety** | Mix of story types: behind-the-scenes, polls, tips, product highlights, testimonials, process reveals, day-in-the-life. No repetitive patterns. | Prompt: "Mix types... Variety is key." Subscription: vary from previous packs. |
| **Completeness** | Every day (1–30) has Idea, Suggested wording, and Story hashtags. No empty blocks. | Output format rule; validation checks for 30 days with required parts. |
| **Date accuracy** | When key date is set (e.g. pop-up 27 March), launch-day Suggested wording does not reference wrong dates (e.g. "opens April" on Day 7). | _validate_caption_quality (covers full doc including stories) flags wrong-month references. |
| **Alignment (when enabled)** | When align_stories_to_captions is on, each day's story supports that day's caption theme. | _generate_stories_aligned receives day summaries from captions. |

## Reference: what "good" looks like

A strong story set:

- Uses concrete, industry-specific ideas (not generic industry filler)
- Phases key dates correctly: teasers before launch day, announcement on the day, thank-you after
- Suggested wording uses the actual dates from DATE_CONTEXT—never invents different ones (e.g. if launch is 27 March, no "opens in April" on launch day)
- Mixes story types: BTS, poll, teaser, educational, engagement
- Uses the real business name consistently—no substitution with example brands

## Maintaining the bar

1. **Prompts:** Quality rules in `services/caption_generator.py` (_generate_stories, _generate_stories_aligned). Do not weaken key-date phasing or brand rules.
2. **Regression tests:** `test_story_key_date_phasing.py` ensures key-date phasing. `test_story_quality_prompts.py` ensures diverse intakes get full quality instructions.
3. **Validation:** _validate_caption_quality runs on full output (captions + stories) and flags date mismatches. _validate_story_quality checks story completeness.
4. **Periodic spot-checks:** When changing story prompts, generate with 2–3 diverse intakes and verify output meets these standards.
