"""
Generate 30 Days of Social Media Captions using OpenAI.
Uses the product framework: Authority, Educational, Brand Personality, Soft Promotion, Engagement.
"""
from typing import Dict, Any, Optional
from openai import OpenAI
from config import Config
from datetime import datetime, timedelta
import re


def _build_date_context(pack_start_date: str) -> Optional[str]:
    """If pack_start_date is YYYY-MM-DD, return a 30-day calendar string for the prompt. Else return None."""
    s = (pack_start_date or "").strip()
    if not s:
        return None
    try:
        start = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    lines = []
    for i in range(30):
        d = start + timedelta(days=i)
        lines.append(f"Day {i + 1} = {d.strftime('%a %d %b %Y')}")
    return "\n".join(lines)


CAPTION_CATEGORIES = [
    "Authority / Expertise",
    "Educational / Value",
    "Brand Personality",
    "Soft Promotion",
    "Engagement",
]

# Approximate count per category over 30 days
CATEGORY_COUNTS = {
    "Authority / Expertise": 6,
    "Educational / Value": 6,
    "Brand Personality": 6,
    "Soft Promotion": 6,
    "Engagement": 6,
}


LANGUAGE_INSTRUCTIONS = {
    "English (UK)": "Use British English (UK) throughout: spelling (e.g. colour, favour, organise, centre, recognised), punctuation (single quotes for quotations where appropriate), and vocabulary (e.g. whilst, amongst, towards). Do not use American spellings or conventions.",
    "English (US)": "Use American English (US) throughout: spelling (e.g. color, favor, organize, center, recognized), punctuation (double quotes for quotations where appropriate), and vocabulary (e.g. while, among, toward). Do not use British spellings or conventions.",
    "Spanish": "Write ALL captions and content in Spanish. Use clear, professional Spanish appropriate for social media. Match the regional variety to the audience if specified (e.g. Spain vs Latin American Spanish).",
    "French": "Write ALL captions and content in French. Use clear, professional French appropriate for social media. Match the regional variety to the audience if specified (e.g. France vs Canadian French).",
    "German": "Write ALL captions and content in German. Use clear, professional German appropriate for social media. Use formal 'Sie' unless the brand voice suggests informal 'du'.",
    "Portuguese": "Write ALL captions and content in Portuguese. Prefer Brazilian Portuguese unless the audience suggests European Portuguese. Use clear, professional language appropriate for social media.",
}


def _build_system_prompt(intake: Dict[str, Any]) -> str:
    lang = (intake.get("caption_language") or "English (UK)").strip()
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
    return f"""You are a senior content strategist and conversion-focused copywriter. You write social media captions for professionals and founders.

{lang_instruction}

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

Multi-platform (captions for every platform every day): When the client has more than one platform (e.g. Instagram & Facebook, LinkedIn, Pinterest), you must write one caption for EACH platform on EACH day. So for each day 1–30: first "## Day N — [Category]", then one full caption block (Platform, hook, caption, Hashtags if requested) for platform A, then the same for platform B, then platform C, etc. Each day therefore contains as many captions as there are platforms — all for that same day. "Instagram & Facebook" counts as one platform: use that label and write one caption that works for both. Rotate through the five categories across the 30 days so the mix is balanced (roughly 6 days per category). Do not duplicate the same caption across platforms; tailor each to the platform (e.g. LinkedIn more professional, TikTok shorter, Pinterest keyword-rich).

TikTok: When TikTok is one of the client's platforms, for days assigned to TikTok write shorter, punchier captions (1–3 short lines; hook in the first line; clear CTA). Use fewer hashtags and TikTok-appropriate tag style for those days.

Pinterest: When Pinterest is one of the client's platforms, for days assigned to Pinterest write search-friendly, keyword-rich descriptions (clear title and description; include relevant keywords and a clear CTA/link where appropriate).

Hashtag guidance (when HASHTAGS_REQUESTED is true): Choose hashtags that support algorithm reach and discovery. Use a mix of (a) niche/specific tags relevant to the client's industry and audience, and (b) broader, high-activity tags where the content fits. Match hashtags to the caption topic and the platform for that day (e.g. LinkedIn vs Instagram vs TikTok norms). Avoid banned or spammy tags. Hashtag count per caption must fall strictly between HASHTAG_MIN and HASHTAG_MAX (inclusive).

Single platform: Write 30 distinct captions (one per day). Multiple platforms: Write 30 × [number of platforms] distinct captions — for each day, one caption per platform. Rotate through the five categories across days so the mix is balanced (roughly 6 days per category). Every caption must be tailored to the client's business, audience, voice, the platform it is for, and goal. Each caption must also be linguistically distinct: vary your vocabulary, sentence openings, and structure so the full set avoids repetition and feels varied. When a business name is provided, use it naturally where it fits (e.g. sign-offs, occasional mentions like "At [name] we...") — don't force it into every caption. No placeholder text. No "[insert X]". Each caption should be 2–6 short paragraphs (or 1–3 lines for TikTok days), copy-paste ready.

Launch/event phasing (when LAUNCH_EVENT is provided): Days before launch = pre-launch (build anticipation, teasers, countdown). Launch day = announcement, go-live. Days after launch = post-launch (thank-you, feedback, early results — NOT hype or anticipation)."""


def extract_day_categories_from_captions_md(captions_md: str) -> list:
    """Extract the category for each day (1–30) from captions markdown. Returns a list of 30 strings (category names); missing days are empty strings."""
    categories_by_day = {}
    for line in captions_md.splitlines():
        m = re.match(r"^##\s*Day\s+(\d+)\s*[—-]\s*(.+)$", line.strip())
        if not m:
            continue
        try:
            day_num = int(m.group(1))
        except ValueError:
            continue
        if 1 <= day_num <= 30:
            categories_by_day[day_num] = m.group(2).strip()
    return [categories_by_day.get(i, "") for i in range(1, 31)]


def _build_user_prompt(
    intake: Dict[str, Any],
    day_start: int = 1,
    day_end: int = 30,
    previous_pack_themes: Optional[list] = None,
) -> str:
    """Build user prompt. If day_start/day_end are not 1–30, generate full doc; else generate only that range."""
    from datetime import datetime
    month_year = datetime.utcnow().strftime("%B %Y")
    include_hashtags = intake.get("include_hashtags", True)
    if isinstance(include_hashtags, str) and include_hashtags.lower() in ("false", "0", "no", "off"):
        include_hashtags = False
    hashtag_min = max(1, min(30, int(intake.get("hashtag_min") or 3)))
    hashtag_max = max(0, min(30, int(intake.get("hashtag_max") or 10)))
    if hashtag_min > hashtag_max:
        hashtag_max = hashtag_min
    platform_raw = (intake.get("platform") or "").strip()
    platform_list = [p.strip() for p in platform_raw.split(",") if p.strip()] if platform_raw else []
    if not platform_list:
        platform_list = ["Not specified"]

    range_note = ""
    if 1 <= day_start <= day_end <= 30 and (day_start != 1 or day_end != 30):
        range_note = f"\n\nGenerate ONLY days {day_start} to {day_end} (inclusive). Output only those day sections (## Day N — ... through ## Day {day_end} — ...). No title, no intake summary — just the day blocks.\n"

    parts = [
        f"Generate the full 30-day caption document for this client. Current month/year: {month_year}.",
        f"HASHTAGS_REQUESTED: {str(include_hashtags).lower()}",
        f"HASHTAG_MIN: {hashtag_min}",
        f"HASHTAG_MAX: {hashtag_max}",
        "",
        "INTAKE:",
        f"- Business name: {intake.get('business_name', '') or 'Not specified'}",
        f"- Business type: {intake.get('business_type', '')}",
        f"- What they offer (one sentence): {intake.get('offer_one_line', '')}",
        f"- Primary audience: {intake.get('audience', '')}",
        f"- Consumer age range (if applicable): {intake.get('consumer_age_range', '') or 'Not specified'}",
        f"- What audience cares about: {intake.get('audience_cares', '')}",
        f"- Platform(s): {platform_raw or 'Not specified'}",
        f"- Platform habits: {intake.get('platform_habits', '') or 'None'}",
        f"- Goal for the month: {intake.get('goal', '')}",
        f"- Caption language: {intake.get('caption_language', 'English (UK)')}",
    ]
    if len(platform_list) > 1:
        parts.append("")
        parts.append(
            f"For EACH day (1–30), write one caption for EACH of these platforms: {', '.join(platform_list)}. "
            "So each day has " + str(len(platform_list)) + " captions — one per platform. Use **Platform:** [exact label] before each caption. "
            "'Instagram & Facebook' is one platform: one caption for both. Tailor each caption to the platform (e.g. LinkedIn tone vs TikTok short punchy vs Pinterest keyword-rich)."
        )
    elif len(platform_list) == 1 and platform_list[0] not in ("Not specified", ""):
        parts.append("")
        parts.append("Write one caption per day (30 total). Label each with **Platform:** " + platform_list[0] + ".")
    examples = (intake.get("caption_examples") or "").strip()
    if examples:
        parts.extend([
            "",
            "EXAMPLES OF DESIRED CAPTIONS (match this style, tone, and structure where relevant):",
            examples,
        ])

    # Launch/event: pass description (with dates) to AI for phasing
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if launch_desc:
        parts.extend([
            "",
            "KEY_DATE_EVENTS (user included dates in description):",
            launch_desc,
            "",
            "Phase content by the dates above: BEFORE = anticipation, teasers; ON/DURING = announce, promote; AFTER = thank-you, feedback. Support multiple events if listed.",
        ])

    # Always pass date context: assume Day 1 = today (generation day) so captions are date-aware
    date_context = _build_date_context(datetime.utcnow().strftime("%Y-%m-%d"))
    if date_context:
        parts.extend([
            "",
            "DATE_CONTEXT (the client's 30 days start on a specific date; use when it adds value):",
            date_context,
            "",
            "When DATE_CONTEXT is provided, you may reference the actual day or date where it helps (e.g. weekday, weekend, end of month). Do not force date references into every caption; use only when relevant and natural.",
        ])

    # Subscription variety: avoid repeating the same day-by-day category pattern as previous packs
    if previous_pack_themes and len(previous_pack_themes) > 0:
        lines = []
        for i, pack in enumerate(previous_pack_themes[:6], 1):  # last 6 packs max
            day_cats = None
            if isinstance(pack, (list, tuple)) and len(pack) >= 30:
                day_cats = [str(c).strip() or "—" for c in pack[:30]]
            elif isinstance(pack, dict) and pack.get("day_categories"):
                raw = list(pack["day_categories"])[:30]
                day_cats = [str(c).strip() or "—" for c in raw]
                while len(day_cats) < 30:
                    day_cats.append("—")
            if day_cats:
                lines.append(f"Previous pack {i}: " + ", ".join(f"D{j+1}:{day_cats[j]}" for j in range(30)))
        if lines:
            parts.extend([
                "",
                "SUBSCRIPTION VARIETY — this client has received previous packs. Previous day-by-day category patterns:",
                *lines,
                "",
                "This month, vary the mix: use a different order and distribution of the five categories so content is not repetitive. Avoid using the same category on the same day number where possible. Keep the same approximate balance (roughly 6 per category) but shuffle which days get which category.",
                "",
                "Also vary the actual content: use different angles, topics, hooks, examples, and phrasing within each category. Do not repeat the same ideas, openers, or proof points they had in previous packs. Each caption should feel fresh and distinct from what they received in earlier months.",
            ])

    parts.extend([
        "",
        "Output the complete markdown document only. No preamble or explanation."
    ])
    return "\n".join(parts) + range_note


def _build_doc_header(intake: Dict[str, Any]) -> str:
    """Build title, subtitle, and intake summary so we can prepend to chunked output."""
    from datetime import datetime
    month_year = datetime.utcnow().strftime("%B %Y")
    business = (intake.get("business_name") or "").strip() or "Client"
    lines = [
        "# 30 Days of Social Media Captions",
        f"{business} | {month_year}",
        "---",
        "INTAKE SUMMARY",
        "---",
        f"- Business: {intake.get('business_name', '') or 'Not specified'}",
        f"- Audience: {intake.get('audience', '') or 'Not specified'}",
        f"- Voice: {intake.get('voice_words', '') or intake.get('voice_avoid', '') or 'Not specified'}",
        f"- Language: {intake.get('caption_language', 'English (UK)')}",
        f"- Platform(s): {(intake.get('platform') or '').strip() or 'Not specified'}",
        f"- Goal: {intake.get('goal', '') or 'Not specified'}",
    ]
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if launch_desc:
        lines.append(f"- Key date: {launch_desc}")
    lines.extend([
        "---",
        "CAPTIONS",
        "---",
    ])
    return "\n".join(lines) + "\n"


class CaptionGenerator:
    """Generate 30 captions from intake using OpenAI. Uses 3 chunks to avoid timeouts and token limits."""

    CHUNKS = [(1, 10), (11, 20), (21, 30)]
    MAX_TOKENS_PER_CHUNK = 6000

    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL

    def generate(self, intake: Dict[str, Any], previous_pack_themes: Optional[list] = None) -> str:
        """
        Generate full 30-day caption document as markdown in 3 API calls (days 1–10, 11–20, 21–30).
        If include_stories and platform has Instagram & Facebook, appends 30 Story prompts.
        previous_pack_themes: for subscriptions, list of previous packs' day categories (each a list of 30 or dict with day_categories) so this month can vary.
        Raises on API error.
        """
        system = _build_system_prompt(intake)
        header = _build_doc_header(intake)
        parts = [header]
        for day_start, day_end in self.CHUNKS:
            user = _build_user_prompt(intake, day_start=day_start, day_end=day_end, previous_pack_themes=previous_pack_themes)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.6,
                max_tokens=self.MAX_TOKENS_PER_CHUNK,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError(f"OpenAI returned empty content for days {day_start}-{day_end}")
            parts.append(content)
        result = "\n".join(parts)

        # Stories add-on: when IG & FB selected and include_stories
        platform_raw = (intake.get("platform") or "").strip().lower()
        include_stories = bool(intake.get("include_stories"))
        align_stories = bool(intake.get("align_stories_to_captions"))
        has_ig_fb = "instagram" in platform_raw or "facebook" in platform_raw
        if include_stories and has_ig_fb:
            if align_stories:
                stories_md = self._generate_stories_aligned(intake, result, is_subscription_variety=bool(previous_pack_themes))
            else:
                stories_md = self._generate_stories(intake, is_subscription_variety=bool(previous_pack_themes))
            if stories_md:
                result = result + "\n\n" + stories_md
        return result

    def _generate_stories(self, intake: Dict[str, Any], is_subscription_variety: bool = False) -> str:
        """Generate 30 one-line Story prompts for Instagram/Facebook."""
        lang = (intake.get("caption_language") or "English (UK)").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
        business = (intake.get("business_name") or "").strip() or "Client"
        month_year = datetime.utcnow().strftime("%B %Y")
        date_context = _build_date_context(datetime.utcnow().strftime("%Y-%m-%d"))
        date_block = ""
        if date_context:
            date_block = f"""

DATE_CONTEXT (their 30 days start on a specific date; use when relevant, e.g. weekday/weekend):
{date_context}

You may reference the actual day/date where it helps (e.g. Monday tip, weekend post). Use only when natural.
"""
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"
        prompt = f"""Generate 30 one-line Story prompts for Instagram/Facebook Stories. One prompt per day (Day 1–30).

{lang_instruction}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}
{date_block}
{variety_note}

Each prompt should be a single short line (5–15 words) suggesting what to post in a Story that day. Mix: behind-the-scenes, tips, questions, polls, product highlights, testimonials, process reveals, day-in-the-life. Variety is key.

Output format — markdown only:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** [one-line prompt]
**Day 2:** [one-line prompt]
...
**Day 30:** [one-line prompt]
---

Output the complete list only. No preamble."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You write concise, actionable social media content prompts."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            content = (response.choices[0].message.content or "").strip()
            return content if content else ""
        except Exception as e:
            print(f"[CaptionGenerator] Stories generation failed: {e}")
            return ""

    def _generate_stories_aligned(self, intake: Dict[str, Any], captions_md: str, is_subscription_variety: bool = False) -> str:
        """Generate 30 Story prompts with explicit day-by-day alignment to captions."""
        # Extract \"## Day N — ...\" headings to summarise each day's caption.
        day_summaries: Dict[int, str] = {}
        for line in captions_md.splitlines():
            m = re.match(r\"^##\\s*Day\\s+(\\d+)\\s*[—-]\\s*(.+)$\", line.strip())
            if not m:
                continue
            try:
                day_num = int(m.group(1))
            except ValueError:
                continue
            if 1 <= day_num <= 30:
                day_summaries[day_num] = m.group(2).strip()

        summary_lines = []
        for i in range(1, 31):
            if i in day_summaries:
                summary_lines.append(f\"Day {i}: {day_summaries[i]}\")

        summaries_block = \"\\n\".join(summary_lines)

        lang = (intake.get(\"caption_language\") or \"English (UK)\").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS[\"English (UK)\"])
        business = (intake.get(\"business_name\") or \"\").strip() or \"Client\"
        month_year = datetime.utcnow().strftime(\"%B %Y\")
        date_context = _build_date_context(datetime.utcnow().strftime(\"%Y-%m-%d\"))
        date_block = \"\"
        if date_context:
            date_block = f\"\"\"

DATE_CONTEXT (their 30 days start on a specific date; use when relevant):
{date_context}

You may reference the actual day/date where it helps. Use only when natural.
\"\"\"
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"

        prompt = f\"\"\"Generate 30 one-line Story prompts for Instagram/Facebook Stories. One prompt per day (Day 1–30).

{lang_instruction}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}
{date_block}
{variety_note}

Here is the theme or focus for each day's main caption:
{summaries_block}

For each Day N, write a Story prompt that explicitly supports and reinforces that day's caption. Think of it as the visibility layer between posts: behind-the-scenes, polls, quick proof, or micro-examples that keep the message active.

Each prompt should be a single short line (5–20 words). Mix: behind-the-scenes, tips, questions, polls, product highlights, testimonials, process reveals, day-in-the-life. Variety is key, but always tied to that day's caption theme.

Output format — markdown only:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** [one-line prompt]
**Day 2:** [one-line prompt]
...
**Day 30:** [one-line prompt]
---

Output the complete list only. No preamble.\"\"\"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {\"role\": \"system\", \"content\": \"You write concise, actionable social media content prompts that align with an existing captions plan.\"},
                    {\"role\": \"user\", \"content\": prompt},
                ],
                temperature=0.7,
                max_tokens=1800,
            )
            content = (response.choices[0].message.content or \"\").strip()
            return content if content else \"\"
        except Exception as e:
            print(f\"[CaptionGenerator] Aligned stories generation failed: {e}\")
            return \"\"
