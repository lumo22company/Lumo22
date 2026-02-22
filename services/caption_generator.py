"""
Generate 30 Days of Social Media Captions using OpenAI.
Uses the product framework: Authority, Educational, Brand Personality, Soft Promotion, Engagement.
"""
from typing import Dict, Any
from openai import OpenAI
from config import Config
from datetime import datetime


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


def _build_system_prompt() -> str:
    return """You are a senior content strategist and conversion-focused copywriter. You write social media captions for professionals and founders.

Use British English (UK) throughout: spelling (e.g. colour, favour, organise, centre, recognised), punctuation (single quotes for quotations where appropriate), and vocabulary (e.g. whilst, amongst, towards). Do not use American spellings or conventions.

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


def _build_user_prompt(intake: Dict[str, Any], day_start: int = 1, day_end: int = 30) -> str:
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

    def generate(self, intake: Dict[str, Any]) -> str:
        """
        Generate full 30-day caption document as markdown in 3 API calls (days 1–10, 11–20, 21–30).
        Raises on API error.
        """
        system = _build_system_prompt()
        header = _build_doc_header(intake)
        parts = [header]
        for day_start, day_end in self.CHUNKS:
            user = _build_user_prompt(intake, day_start=day_start, day_end=day_end)
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
        return "\n".join(parts)
