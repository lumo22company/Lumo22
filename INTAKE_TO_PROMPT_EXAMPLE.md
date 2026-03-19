# How the intake form becomes a prompt

**In one sentence:** The form answers are turned into two text blocks—a **system prompt** (who the AI is and how it must write) and a **user prompt** (this client’s details and what to output). Those two blocks are sent to the AI three times (once per chunk: days 1–10, 11–20, 21–30) to generate the 30-day captions.

---

## Example prompt (quick view)

For the **Launch Test / cake** intake (product brand, “I make cakes”, 4 platforms, key date “Free cakes for kids on 30th March”), the prompts look like this. **Full versions are in [Full prompt example](#full-prompt-example-real-output-from-code) below.**

**System prompt (opening):**
```
You are a top social media manager for cake makers and bakeries. You write scroll-stopping, conversion-focused captions that fit the brand and drive engagement. You are also a senior content strategist and conversion-focused copywriter. You write social media captions.

Use American English (US) throughout: ...
Tone: confident, editorial, modern, premium. ...
[... then: five categories, output format, completeness, multi-platform, hashtags, business relevance, launch phasing]
```

**User prompt (opening):**
```
Generate the full 30-day caption document for this client. Current month/year: March 2026.
HASHTAGS_REQUESTED: true
HASHTAG_MIN: 3
HASHTAG_MAX: 10

INTAKE (use these normalized forms in captions—do not repeat ALL CAPS):
- Business name: Launch Test
- Business type: Product brand / E-commerce
- What they offer (one sentence): I make cakes
- Primary audience: Small business owners, Consumers
...
RELEVANCE: Every caption must be clearly about this business...
[... then: platform instruction, KEY_DATE_EVENTS, IMPORTANT Day 13, DATE_CONTEXT, chunk range]
```

---

## How it works (simple flow)

```
Form submitted  →  intake dict (business name, offer, audience, platforms, goal, key date, etc.)
                            ↓
         ┌──────────────────┴──────────────────┐
         ↓                                      ↓
   System prompt                           User prompt
   (role + rules + format)                 (this client’s INTAKE + instructions)
         ↓                                      ↓
         └──────────────────┬──────────────────┘
                            ↓
              chat_completion(system, user)  →  AI returns markdown
                            ↓
              Markdown parsed  →  PDF built (caption_pdf.py)
```

- **System prompt:** Built once per order from `_build_system_prompt(intake)`. Tells the AI its role, language, tone, the five categories, output format, and rules (completeness, business relevance, launch phasing).
- **User prompt:** Built once per chunk from `_build_user_prompt(intake, day_start, day_end, ...)`. Contains this client’s INTAKE (normalized), hashtag settings, platform list, key date if any, date context, and the instruction “output only days X–Y” for that chunk.

So: **same system prompt** for all three chunks; **same user prompt** except the last line (“Generate ONLY days 1 to 10” vs 11–20 vs 21–30).

---

## What changes per client vs what’s fixed

| Part of the prompt | What changes per client | What’s fixed |
|--------------------|--------------------------|--------------|
| **System prompt** | (1) First line: “You are a top social media manager for **[niche]**…” (from business type / offer). (2) Language paragraph (e.g. US vs UK English from form). | Tone, categories, output format, completeness, relevance rules, launch phasing. |
| **User prompt** | INTAKE block (business name, type, offer, audience, platforms, goal, etc.), KEY_DATE_EVENTS + IMPORTANT (if they added a key date), DATE_CONTEXT (calendar), platform list. | “Generate the full 30-day document…”, HASHTAGS_REQUESTED/MIN/MAX, RELEVANCE line, “Output complete markdown only”, chunk range line. |

Form values are **normalized** before going into the prompt (e.g. ALL CAPS → title/sentence case).

---

## Form fields → where they go in the prompt

| Form field | Intake key | Used in |
|------------|------------|--------|
| Business name | `business_name` | System (role niche), user INTAKE, doc header |
| Business type | `business_type` | System (role niche), user INTAKE |
| What they offer (one sentence) | `offer_one_line` | System (role niche), user INTAKE |
| Primary audience | `audience` | User INTAKE, doc header |
| Consumer age range | `consumer_age_range` | User INTAKE |
| What audience cares about | `audience_cares` | User INTAKE |
| Platforms | `platform` | User INTAKE + platform instruction |
| Platform habits | `platform_habits` | User INTAKE |
| Goal for the month | `goal` | User INTAKE, doc header |
| Key date / events | `launch_event_description` | User KEY_DATE_EVENTS + IMPORTANT (day number), doc header |
| Caption language | `caption_language` | System (language paragraph) |
| Include hashtags | `include_hashtags` | User HASHTAGS_REQUESTED |
| Hashtag min/max | `hashtag_min`, `hashtag_max` | User HASHTAG_MIN, HASHTAG_MAX |
| Example captions (optional) | `caption_examples` | User (EXAMPLES block) |
| Voice words / avoid | `voice_words`, `voice_avoid` | User INTAKE (Voice / tone to use, Words / style to avoid), doc header, system (tone override) |

---

## System prompt — what each part does

The **system prompt** sets the AI’s identity and the rules it must follow. Below is what each section is for.

1. **Role (dynamic)**  
   - “You are a top social media manager for **[niche]**…” (e.g. cake makers and bakeries, coaches and consultants).  
   - **Purpose:** Nail the type of business so captions feel on-industry.

2. **Role (fixed)**  
   - “You are also a senior content strategist and conversion-focused copywriter. You write social media captions.”  
   - **Purpose:** Reinforce strategy and conversion; stays relevant to whoever the client is (from the intake).

3. **Language**  
   - One paragraph: US vs UK English (spelling, punctuation, vocabulary).  
   - **Purpose:** Match the form’s “Caption language”.

4. **Tone**  
   - Confident, editorial, no emojis/clichés, no generic AI speak.  
   - **Purpose:** Consistent voice across all captions.

5. **Variety**  
   - Different openers, phrasing, and angles each day.  
   - **Purpose:** Avoid repetition across 30 days.

6. **Five categories**  
   - Authority, Educational, Brand personality, Soft promotion, Engagement; ~6 days each.  
   - **Purpose:** Structure the 30-day plan.

7. **Output format**  
   - Markdown: title, intake summary, then per day “## Day N — [Category]”, then per platform “**Platform:**”, “**Caption:**”, “**Hashtags:**” (if on).  
   - **Purpose:** So we can parse the response and build the PDF.

8. **Completeness**  
   - Every day, every platform: full caption (and hashtags when requested). No empty blocks.  
   - **Purpose:** No missing days/platforms in the PDF.

9. **Multi-platform / TikTok / Pinterest**  
   - One caption per platform per day; TikTok shorter; Pinterest keyword-rich.  
   - **Purpose:** Platform-appropriate content.

10. **Hashtag guidance**  
    - Min–max count, mix of niche + broad, no banned tags.  
    - **Purpose:** Consistent hashtag quality.

11. **Business relevance**  
    - Captions must be clearly about *this* business (what they sell, who they serve). No generic “founder/strategy” fluff.  
    - **Purpose:** Avoid off-topic or vague captions.

12. **Launch phasing**  
    - If there’s a key date: pre-launch → launch day → post-launch.  
    - **Purpose:** Align content with their event (e.g. “Free cakes for kids on 30th March”).

---

## User prompt — what each part does

The **user prompt** gives the AI this client’s details and the exact task for this chunk.

1. **Task + month/year**  
   - “Generate the full 30-day caption document for this client. Current month/year: March 2026.”  
   - **Purpose:** Set the frame for the pack.

2. **HASHTAGS_REQUESTED, HASHTAG_MIN, HASHTAG_MAX**  
   - Copied from the form.  
   - **Purpose:** So the model knows whether to add hashtags and the count range.

3. **INTAKE**  
   - Bullet list: business name, type, offer, audience, voice words, voice avoid, platforms, goal, language, etc. (normalized).  
   - **Purpose:** All client-specific facts in one place, including tone to use and style to avoid.

4. **RELEVANCE**  
   - Reminder: every caption must be clearly about this business; use concrete details from the intake.  
   - **Purpose:** Reinforce the system-prompt “business relevance” rule.

5. **VOICE** (when voice/avoid are in intake)  
   - Match the client’s voice words and avoid their listed words/style; when goal is leads or inquiries, include a clear next step where natural.  
   - **Purpose:** Ensure tone matches the form and CTAs support the client’s goal.

6. **Platform instruction**  
   - “For EACH day write one caption for EACH of these platforms: …” with exact labels.  
   - **Purpose:** Correct number of captions per day and correct platform names in output.  
   - “For EACH day write one caption for EACH of these platforms: …” with exact labels.  
   - **Purpose:** Correct number of captions per day and correct platform names in output.

7. **KEY_DATE_EVENTS** (if they filled a key date)  
   - Their event text, e.g. “Free cakes for kids on 30th March”.  
   - **Purpose:** Tell the model what to phase content around.

8. **IMPORTANT** (if we parsed a date)  
   - “The client’s key date above falls on Day 13. Write pre-launch for days 1–12, launch for Day 13, post-launch for days 14–30.”  
   - **Purpose:** Pin the event to a specific day so phasing is correct.

9. **DATE_CONTEXT**  
   - “Day 1 = Wed 18 Mar 2026” … “Day 30 = Thu 16 Apr 2026”.  
   - **Purpose:** Let the model use real dates when it helps (e.g. “this Saturday”).

10. **Output instruction**  
   - “Output the complete markdown only. No preamble or explanation.”  
   - **Purpose:** Avoid intros or commentary before the captions.

11. **Chunk range**  
    - “Generate ONLY days 1 to 10 (inclusive). Output only those day sections … No title, no intake summary — just the day blocks.”  
    - **Purpose:** For chunk 1 we only want days 1–10; chunks 2 and 3 ask for 11–20 and 21–30 the same way.

---

## Full prompt example (real output from code)

**Scroll down to see the complete system and user prompt.** This is the exact text sent to the AI for the Launch Test / cake client (chunk 1: days 1–10). Same intake as in the quick view above.

Example client: **Launch Test**, product brand / e-commerce, “I make cakes”, 4 platforms, goal **Launch visibility**, key date **Free cakes for kids on 30th March**, pack start **2026-03-18**.

### Full system prompt

```
You are a top social media manager for cake makers and bakeries. You write scroll-stopping, conversion-focused captions that fit the brand and drive engagement. You are also a senior content strategist and conversion-focused copywriter. You write social media captions.

Use American English (US) throughout: spelling (e.g. color, favor, organize, center, recognized), punctuation (double quotes for quotations where appropriate), and vocabulary (e.g. while, among, toward). Do not use British spellings or conventions.

Tone: confident, editorial, modern, premium. No emojis. No buzzwords or marketing clichés. Smart, human, intelligent. Avoid hype and generic AI language.

Variety and anti-repetition: Every caption must feel fresh and distinct. Use a wide range of vocabulary—avoid reusing the same words, phrases, hooks, or openings across days. Vary sentence structures, transitions, and sign-offs. No two captions should start with the same opener (e.g. avoid "Here's the thing" or "Let's talk about" repeatedly). Rotate through different angles, examples, and approaches. If you've used a phrase in one caption, use different wording in the next.

You produce a 30-day caption plan using exactly these five categories, distributed across the month:
- Authority / Expertise (establish credibility, perspective, experience)
- Educational / Value (teach something useful, answer a real question)
- Brand Personality (process, philosophy, behind-the-scenes)
- Soft Promotion (invite a next step, mention offer, low pressure)
- Engagement (questions, prompts, conversation starters)

Output format: You must respond with a single markdown document. Structure:
1. Title: "# 30 Days of Social Media Captions"
2. Subtitle: "[Business name from intake, or a brief identifier] | [Current month year]"
3. Section "---" then "INTAKE SUMMARY" then "---" then bullet lines: Business, Audience, Voice, Platform(s), Goal (from the intake).
4. Section "---" then "CAPTIONS" then "---"
5. For each day (1–30): "## Day N — [Category]" then for each platform (see below) repeat: "**Platform:** [exact platform label]" then "**Caption:** [first line of caption]" then a blank line then the full caption text (ready to copy-paste). If HASHTAGS_REQUESTED is true, then a blank line then "**Hashtags:** [MIN–MAX hashtags for this caption, comma-separated or space-separated]". Then "---" only after all platforms for that day are done. If HASHTAGS_REQUESTED is false, do NOT include any **Hashtags:** line.

CRITICAL — Completeness: Every day (1–30) must have exactly one caption block per platform. Never leave a **Caption:** or **Hashtags:** line empty. Every platform for every day must have a full, copy-paste-ready caption (2–6 short paragraphs, or 1–3 lines for TikTok). If HASHTAGS_REQUESTED is true, every caption must include a **Hashtags:** line with at least MIN and at most MAX hashtags. If you are generating only a range of days (e.g. 11–20), every day in that range must still have every platform complete. Do not output placeholder text or skip any day/platform.

Multi-platform (captions for every platform every day): When the client has more than one platform (e.g. Instagram & Facebook, LinkedIn, Pinterest), you must write one caption for EACH platform on EACH day. So each day 1–30: first "## Day N — [Category]", then one full caption block (Platform, hook, caption, Hashtags if requested) for platform A, then the same for platform B, then platform C, etc. Each day therefore contains as many captions as there are platforms — all for that same day. "Instagram & Facebook" counts as one platform: use that label and write one caption that works for both. Rotate through the five categories across the 30 days so the mix is balanced (roughly 6 days per category). Do not duplicate the same caption across platforms; tailor each to the platform (e.g. LinkedIn more professional, TikTok shorter, Pinterest keyword-rich).

TikTok: When TikTok is one of the client's platforms, for days assigned to TikTok write shorter, punchier captions (1–3 short lines; hook in the first line; clear CTA). Use fewer hashtags and TikTok-appropriate tag style for those days.

Pinterest: When Pinterest is one of the client's platforms, for days assigned to Pinterest write search-friendly, keyword-rich descriptions (clear title and description; include relevant keywords and a clear CTA/link where appropriate).

Hashtag guidance (when HASHTAGS_REQUESTED is true): Every single caption MUST include a **Hashtags:** line. Never omit hashtags for any day or platform. Choose hashtags that support algorithm reach and discovery. Use a mix of (a) niche/specific tags relevant to the client's industry and audience, and (b) broader, high-activity tags where the content fits. Match hashtags to the caption topic and the platform for that day (e.g. LinkedIn vs Instagram vs TikTok norms). Avoid banned or spammy tags. Hashtag count per caption must fall strictly between HASHTAG_MIN and HASHTAG_MAX (inclusive).

Single platform: Write 30 distinct captions (one per day). Multiple platforms: Write 30 × [number of platforms] distinct captions — for each day, one caption per platform. Rotate through the five categories across days so the mix is balanced (roughly 6 days per category). Every caption must be tailored to the client's business, audience, voice, the platform it is for, and goal. Each caption must also be linguistically distinct: vary your vocabulary, sentence openings, and structure so the full set avoids repetition and feels varied. When a business name is provided, use it naturally where it fits (e.g. sign-offs, occasional mentions like "At [name] we...") — don't force it into every caption. No placeholder text. No "[insert X]". Each caption should be 2–6 short paragraphs (or 1–3 lines for TikTok days), copy-paste ready.

Business relevance (CRITICAL): Every caption must be clearly about THIS business—what they actually sell or do, who they serve, and their specific product or service. Do not write generic "founder", "strategy", "building a brand", or "scaling a business" captions that could apply to any company. If the business is cakes and baking, reference cakes, baking, ingredients, orders, customers, flavours, etc. If the business is coaching, reference coaching, clients, sessions, outcomes. Match the vocabulary and examples to the business type and "What they offer" from the intake. A reader should immediately understand which industry and offer the caption is for.

Launch/event phasing (when LAUNCH_EVENT is provided): Days before launch = pre-launch (build anticipation, teasers, countdown). Launch day = announcement, go-live. Days after launch = post-launch (thank-you, feedback, early results — NOT hype or anticipation).
```

### Full user prompt (chunk 1: days 1–10 only)

```
Generate the full 30-day caption document for this client. Current month/year: March 2026.
HASHTAGS_REQUESTED: true
HASHTAG_MIN: 3
HASHTAG_MAX: 10

INTAKE (use these normalized forms in captions—do not repeat ALL CAPS):
- Business name: Launch Test
- Business type: Product brand / E-commerce
- What they offer (one sentence): I make cakes
- Primary audience: Small business owners, Consumers
- Consumer age range (if applicable): 30+
- What audience cares about: Looking at my great cakes
- Platform(s): Instagram & Facebook, LinkedIn, TikTok, Pinterest
- Platform habits: None
- Goal for the month: Launch visibility
- Caption language: English (US)

RELEVANCE: Every caption must be clearly about this business—their product/service, their audience, their offer. Do not write generic business/strategy/founder captions that could apply to any company. Use concrete details from the intake (e.g. if they offer cakes, reference cakes, baking, ingredients, orders; if they offer coaching, reference sessions, clients, outcomes). A reader should know which industry and offer the caption is for.

For EACH day (1–30), write one caption for EACH of these platforms: Instagram & Facebook, LinkedIn, TikTok, Pinterest. So each day has 4 captions — one per platform. Use **Platform:** [exact label] before each caption. 'Instagram & Facebook' is one platform: one caption for both. Tailor each caption to the platform (e.g. LinkedIn tone vs TikTok short punchy vs Pinterest keyword-rich).

KEY_DATE_EVENTS (user included dates in description):
Free cakes for kids on 30th March

Phase content by the dates above: BEFORE = anticipation, teasers; ON/DURING = announce, promote; AFTER = thank-you, feedback. Support multiple events if listed.

IMPORTANT — The client's key date above falls on Day 13. Write pre-launch/anticipation content for days 1 to 12, launch-day/announcement content for Day 13, and post-launch/thank-you content for days 14 to 30. Do not put launch-day tone on the wrong day.

DATE_CONTEXT (the client's 30 days start on a specific date; use when it adds value):
Day 1 = Wed 18 Mar 2026
Day 2 = Thu 19 Mar 2026
Day 3 = Fri 20 Mar 2026
Day 4 = Sat 21 Mar 2026
Day 5 = Sun 22 Mar 2026
Day 6 = Mon 23 Mar 2026
Day 7 = Tue 24 Mar 2026
Day 8 = Wed 25 Mar 2026
Day 9 = Thu 26 Mar 2026
Day 10 = Fri 27 Mar 2026
Day 11 = Sat 28 Mar 2026
Day 12 = Sun 29 Mar 2026
Day 13 = Mon 30 Mar 2026
Day 14 = Tue 31 Mar 2026
Day 15 = Wed 01 Apr 2026
Day 16 = Thu 02 Apr 2026
Day 17 = Fri 03 Apr 2026
Day 18 = Sat 04 Apr 2026
Day 19 = Sun 05 Apr 2026
Day 20 = Mon 06 Apr 2026
Day 21 = Tue 07 Apr 2026
Day 22 = Wed 08 Apr 2026
Day 23 = Thu 09 Apr 2026
Day 24 = Fri 10 Apr 2026
Day 25 = Sat 11 Apr 2026
Day 26 = Sun 12 Apr 2026
Day 27 = Mon 13 Apr 2026
Day 28 = Tue 14 Apr 2026
Day 29 = Wed 15 Apr 2026
Day 30 = Thu 16 Apr 2026

When DATE_CONTEXT is provided, you may reference the actual day or date where it helps (e.g. weekday, weekend, end of month). Do not force date references into every caption; use only when relevant and natural.

Output the complete markdown document only. No preamble or explanation.

Generate ONLY days 1 to 10 (inclusive). Output only those day sections (## Day N — ... through ## Day 10 — ...). No title, no intake summary — just the day blocks.
```

For **chunk 2** the last line becomes “Generate ONLY days 11 to 20 (inclusive)…”. For **chunk 3**, “Generate ONLY days 21 to 30…”. The doc header (title + intake summary) is built separately and prepended to the combined chunk output before the PDF is built.
