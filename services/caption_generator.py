"""
Generate 30 Days of Social Media Captions using AI (OpenAI or Anthropic Claude).
Uses the product framework: Authority, Educational, Brand Personality, Soft Promotion, Engagement.
"""
from typing import Dict, Any, Optional, Tuple
from config import Config
from services.ai_provider import chat_completion
from datetime import datetime, timedelta
import re

# Month names for parsing key date from intake (e.g. "30th March", "March 30")
_MONTH_NAMES = "january|february|march|april|may|june|july|august|september|october|november|december"
_MONTH_NUM = {m: i for i, m in enumerate(_MONTH_NAMES.split("|"), 1)}


def _normalize_intake_case(s: str, sentence_case: bool = False) -> str:
    """
    Normalize ALL CAPS intake text so PDFs and captions use sentence/title case, not shouting.
    Short phrases (e.g. business name, voice words) -> title case. Longer (e.g. offer, key date) -> sentence case.
    """
    if not s or not isinstance(s, str):
        return (s or "").strip()
    s = s.strip()
    if not s:
        return s
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.8:
        return s
    if sentence_case:
        return s[0].upper() + s[1:].lower()
    return s.title()


def _parse_key_date_from_text(text: str, pack_start_date: str) -> Optional[int]:
    """
    Parse a date from key-date text (e.g. "FREE CAKES FOR KIDS ON 30TH MARCH", "30 March", "March 30").
    Returns the 1-based day number (1–30) if the date falls within the 30-day pack, else None.
    """
    if not text or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None
    text_lower = text.strip().lower()
    # Patterns: "30th march", "30 march", "march 30", "30/03", "30-03"
    day_num = None
    month_num = None
    year = start.year
    # (?:st|nd|rd|th)? day then month name
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(" + _MONTH_NAMES + r")(?:\s+(\d{4}))?", text_lower)
    if m:
        day_num = int(m.group(1))
        month_num = _MONTH_NUM.get(m.group(2))
        if m.group(3):
            year = int(m.group(3))
    if day_num is None or month_num is None:
        m = re.search(r"(" + _MONTH_NAMES + r")\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?", text_lower)
        if m:
            month_num = _MONTH_NUM.get(m.group(1))
            day_num = int(m.group(2))
            if m.group(3):
                year = int(m.group(3))
    if day_num is None or month_num is None:
        return None
    try:
        event_date = datetime(year, month_num, day_num)
    except ValueError:
        return None
    delta = (event_date.date() - start.date()).days
    if 0 <= delta < 30:
        return delta + 1  # 1-based day number
    return None


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
    "Italian": "Write ALL captions and content in Italian. Use clear, professional Italian appropriate for social media. Match the regional variety to the audience if specified (e.g. Italy vs Swiss Italian).",
    "Dutch": "Write ALL captions and content in Dutch. Use clear, professional Dutch appropriate for social media. Match the regional variety to the audience if specified (e.g. Netherlands vs Belgian Dutch).",
    "Polish": "Write ALL captions and content in Polish. Use clear, professional Polish appropriate for social media. Use standard Polish spelling and conventions.",
    "Arabic": "Write ALL captions and content in Arabic. Use clear, professional Modern Standard Arabic (MSA) appropriate for social media, unless the audience suggests a dialect (e.g. Gulf, Levantine). Write right-to-left; the output will be displayed correctly.",
    "Turkish": "Write ALL captions and content in Turkish. Use clear, professional Turkish appropriate for social media. Use modern Turkish spelling (Latin script).",
    "Swedish": "Write ALL captions and content in Swedish. Use clear, professional Swedish appropriate for social media. Use standard Swedish spelling and conventions.",
}


def _role_line_for_intake(intake: Dict[str, Any]) -> str:
    """Build a tailored role line so the AI is framed as an expert for this type of business."""
    business_type = (intake.get("business_type") or "").strip()
    offer = (intake.get("offer_one_line") or "").strip().lower()
    niche = "professional and founder-led brands"
    if business_type:
        # e.g. "Product brand / E-commerce" -> "product brand and e-commerce businesses"
        parts = [p.strip().lower() for p in business_type.split("/") if p.strip()]
        if len(parts) >= 2:
            niche = " and ".join(parts) + " businesses"
        elif len(parts) == 1:
            p = parts[0]
            niche = (p + "s") if not p.endswith("s") else p  # e.g. "service business" -> "service businesses"
    # If offer strongly suggests a niche, use it when it's clearer (e.g. "I make cakes" and no type)
    if offer and len(offer) < 60:
        if any(w in offer for w in ("cake", "baking", "bakery")):
            niche = "cake makers and bakeries"
        elif any(w in offer for w in ("coach", "consulting", "strategy")):
            niche = "coaches and consultants"
    return f"You are a top social media manager for {niche}. You write scroll-stopping, conversion-focused captions that fit the brand and drive engagement."


def _build_system_prompt(intake: Dict[str, Any]) -> str:
    lang = (intake.get("caption_language") or "English (UK)").strip()
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
    role_line = _role_line_for_intake(intake)
    return f"""{role_line} You are also a senior content strategist and conversion-focused copywriter. You write social media captions.

Quality bar: Every caption set must be as tailored and specific as a premium copywriter would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Match the standard of a highly polished 30-day plan.

{lang_instruction}

Tone: confident, editorial, modern, premium. When the client specifies "Voice / tone to use" or "Words / style to avoid" in the intake, match those preferences—they override the default. No emojis. No buzzwords or marketing clichés. Smart, human, intelligent. Avoid hype and generic AI language.

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

Multi-platform (captions for every platform every day): When the client has more than one platform (e.g. Instagram & Facebook, LinkedIn, Pinterest), you must write one caption for EACH platform on EACH day. So for each day 1–30: first "## Day N — [Category]", then one full caption block (Platform, hook, caption, Hashtags if requested) for platform A, then the same for platform B, then platform C, etc. Each day therefore contains as many captions as there are platforms — all for that same day. "Instagram & Facebook" counts as one platform: use that label and write one caption that works for both. Rotate through the five categories across the 30 days so the mix is balanced (roughly 6 days per category). Do not duplicate the same caption across platforms; tailor each to the platform (e.g. LinkedIn more professional, TikTok shorter, Pinterest keyword-rich).

TikTok: When TikTok is one of the client's platforms, for days assigned to TikTok write shorter, punchier captions (1–3 short lines; hook in the first line; clear CTA). Use fewer hashtags and TikTok-appropriate tag style for those days.

Pinterest: When Pinterest is one of the client's platforms, for days assigned to Pinterest write search-friendly, keyword-rich descriptions (clear title and description; include relevant keywords and a clear CTA/link where appropriate).

Hashtag guidance (when HASHTAGS_REQUESTED is true): Every single caption MUST include a **Hashtags:** line. Never omit hashtags for any day or platform. Choose hashtags that support algorithm reach and discovery. Use a mix of (a) niche/specific tags relevant to the client's industry and audience, and (b) broader, high-activity tags where the content fits. Match hashtags to the caption topic and the platform for that day (e.g. LinkedIn vs Instagram vs TikTok norms). Avoid banned or spammy tags. Hashtag count per caption must fall strictly between HASHTAG_MIN and HASHTAG_MAX (inclusive).

Single platform: Write 30 distinct captions (one per day). Multiple platforms: Write 30 × [number of platforms] distinct captions — for each day, one caption per platform. Rotate through the five categories across days so the mix is balanced (roughly 6 days per category). Every caption must be tailored to the client's business, audience, voice, the platform it is for, and goal. Each caption must also be linguistically distinct: vary your vocabulary, sentence openings, and structure so the full set avoids repetition and feels varied. When a business name is provided, use it naturally where it fits (e.g. sign-offs, occasional mentions like "At [name] we...") — don't force it into every caption. No placeholder text. No "[insert X]". Each caption should be 2–6 short paragraphs (or 1–3 lines for TikTok days), copy-paste ready.

Business relevance (CRITICAL): Every caption must be clearly about THIS business—what they actually sell or do, who they serve, and their specific product or service. Do not write generic "founder", "strategy", "building a brand", or "scaling a business" captions that could apply to any company. If the business is cakes and baking, reference cakes, baking, ingredients, orders, customers, flavours, etc. If the business is coaching, reference coaching, clients, sessions, outcomes. Match the vocabulary and examples to the business type and "What they offer" from the intake. A reader should immediately understand which industry and offer the caption is for.

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
    pack_start_date: Optional[str] = None,
) -> str:
    """Build user prompt. If day_start/day_end are not 1–30, generate full doc; else generate only that range.
    pack_start_date: YYYY-MM-DD so Day 1 = this date; used for date context and key-date alignment."""
    from datetime import datetime
    start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
    month_year = datetime.strptime(start_str[:10], "%Y-%m-%d").strftime("%B %Y")
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

    # Normalize ALL CAPS intake so PDFs and captions use sentence/title case
    n = _normalize_intake_case
    business_name = n(intake.get("business_name") or "", sentence_case=False) or "Not specified"
    business_type = n(intake.get("business_type") or "", sentence_case=False)
    offer_one_line = n(intake.get("offer_one_line") or "", sentence_case=True)
    operating_hours = n(intake.get("operating_hours") or "", sentence_case=True)
    audience = n(intake.get("audience") or "", sentence_case=False) or "Not specified"
    consumer_age = n(intake.get("consumer_age_range") or "", sentence_case=False) or "Not specified"
    audience_cares = n(intake.get("audience_cares") or "", sentence_case=True)
    usual_topics = n(intake.get("usual_topics") or "", sentence_case=True)
    platform_habits = n(intake.get("platform_habits") or "", sentence_case=True) or "None"
    goal = n(intake.get("goal") or "", sentence_case=False)
    voice_words = n(intake.get("voice_words") or "", sentence_case=False)
    voice_avoid = n(intake.get("voice_avoid") or "", sentence_case=True)

    parts = [
        f"Generate the full 30-day caption document for this client. Current month/year: {month_year}.",
        f"HASHTAGS_REQUESTED: {str(include_hashtags).lower()}",
        f"HASHTAG_MIN: {hashtag_min}",
        f"HASHTAG_MAX: {hashtag_max}",
        "",
        "INTAKE (use these normalized forms in captions—do not repeat ALL CAPS):",
        f"- Business name: {business_name}",
        f"- Business type: {business_type}",
        f"- What they offer (one sentence): {offer_one_line}",
        f"- Operating hours: {operating_hours or 'Not specified'}",
        f"- Primary audience: {audience}",
        f"- Consumer age range (if applicable): {consumer_age}",
        f"- What audience cares about: {audience_cares}",
        f"- What they usually talk about (content themes): {usual_topics or 'Not specified'}",
        f"- Voice / tone to use: {voice_words or 'Not specified'}",
        f"- Words / style to avoid: {voice_avoid or 'None'}",
        f"- Platform(s): {platform_raw or 'Not specified'}",
        f"- Platform habits: {platform_habits}",
        f"- Goal for the month: {goal}",
        f"- Caption language: {intake.get('caption_language', 'English (UK)')}",
        "",
        "RELEVANCE: Every caption must be clearly about this business—their product/service, their audience, their offer. Do not write generic business/strategy/founder captions that could apply to any company. Use concrete details from the intake (e.g. if they offer cakes, reference cakes, baking, ingredients, orders; if they offer coaching, reference sessions, clients, outcomes). A reader should know which industry and offer the caption is for.",
        "",
        "VOICE: Match the client's voice (Voice / tone to use) and avoid their listed words or style (Words / style to avoid). When the goal is leads or inquiries, include a clear, low-pressure next step (e.g. link in bio, DM, book a call) where it fits naturally.",
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

    # Launch/event: pass description (normalized case) and explicitly map key date to day number
    launch_desc_raw = (intake.get("launch_event_description") or "").strip()
    launch_desc = _normalize_intake_case(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
    key_date_day = _parse_key_date_from_text(launch_desc_raw or launch_desc, start_str) if (launch_desc_raw or launch_desc) else None
    if launch_desc:
        parts.extend([
            "",
            "KEY_DATE_EVENTS (user included dates in description):",
            launch_desc,
            "",
            "Phase content by the dates above: BEFORE = anticipation, teasers; ON/DURING = announce, promote; AFTER = thank-you, feedback. Support multiple events if listed.",
        ])
        if key_date_day is not None:
            parts.extend([
                "",
                f"IMPORTANT — The client's key date above falls on Day {key_date_day}. Write pre-launch/anticipation content for days 1 to {key_date_day - 1}, launch-day/announcement content for Day {key_date_day}, and post-launch/thank-you content for days {key_date_day + 1} to 30. Do not put launch-day tone on the wrong day.",
            ])

    # Date context: Day 1 = pack_start_date so captions are date-aware and key date aligns
    date_context = _build_date_context(start_str)
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


def _build_doc_header(intake: Dict[str, Any], pack_start_date: Optional[str] = None) -> str:
    """Build title, subtitle, and intake summary so we can prepend to chunked output. Uses normalized case (no ALL CAPS)."""
    from datetime import datetime
    n = _normalize_intake_case
    start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
    try:
        month_year = datetime.strptime(start_str[:10], "%Y-%m-%d").strftime("%B %Y")
    except ValueError:
        month_year = datetime.utcnow().strftime("%B %Y")
    business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
    audience = n(intake.get("audience") or "", sentence_case=False) or "Not specified"
    voice = n((intake.get("voice_words") or intake.get("voice_avoid") or "").strip(), sentence_case=False) or "Not specified"
    goal = n(intake.get("goal") or "", sentence_case=False) or "Not specified"
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if launch_desc:
        launch_desc = n(launch_desc, sentence_case=True)
    lines = [
        "# 30 Days of Social Media Captions",
        f"{business} | {month_year}",
        "---",
        "INTAKE SUMMARY",
        "---",
        f"- Business: {business}",
        f"- Audience: {audience}",
        f"- Voice: {voice}",
        f"- Language: {intake.get('caption_language', 'English (UK)')}",
        f"- Platform(s): {(intake.get('platform') or '').strip() or 'Not specified'}",
        f"- Goal: {goal}",
    ]
    if launch_desc:
        lines.append(f"- Key date: {launch_desc}")
    lines.extend([
        "---",
        "CAPTIONS",
        "---",
    ])
    return "\n".join(lines) + "\n"


def _chunk_has_empty_blocks(content: str, include_hashtags: bool) -> bool:
    """Return True if markdown has empty **Caption:** or **Hashtags:** lines (indicates incomplete AI output)."""
    if not content or "**Caption:**" not in content:
        return True
    # Empty Caption: "**Caption:**" followed by optional spaces and newline (no real text)
    if re.search(r"\*\*Caption:\*\*\s*\n", content, re.IGNORECASE):
        return True
    if include_hashtags and re.search(r"\*\*Hashtags?:\*\*\s*\n", content, re.IGNORECASE):
        return True
    return False


def _validate_caption_quality(
    captions_md: str, intake: Dict[str, Any], pack_start_date: str
) -> list:
    """
    Post-generation validation. Returns list of warning strings.
    Catches detectable quality issues (e.g. launch-day content referencing wrong dates).
    Does not block delivery; caller may log warnings.
    """
    warnings = []
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if not launch_desc:
        return warnings
    key_date_day = _parse_key_date_from_text(launch_desc, pack_start_date)
    if key_date_day is None:
        return warnings
    try:
        start = datetime.strptime((pack_start_date or "")[:10], "%Y-%m-%d")
        launch_date = start + timedelta(days=key_date_day - 1)
        expected_month = launch_date.strftime("%B").lower()  # e.g. "march"
        month_order = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
        expected_idx = month_order.index(expected_month) if expected_month in month_order else -1
    except (ValueError, TypeError):
        return warnings

    # Extract content for launch day: ## Day N caption blocks and **Day N:** story lines
    day_content = []
    in_day_block = False
    current_day = 0
    for line in captions_md.splitlines():
        m = re.match(r"^##\s*Day\s+(\d+)\s*[—\-]", line.strip())
        if m:
            current_day = int(m.group(1))
            in_day_block = current_day == key_date_day
            if in_day_block:
                day_content.append(line)
            continue
        m2 = re.match(r"^\*\*Day\s+(\d+):\*\*", line.strip())
        if m2 and int(m2.group(1)) == key_date_day:
            day_content.append(line)
            continue
        if in_day_block and current_day == key_date_day:
            # Still in caption block for this day (until next ## Day)
            day_content.append(line)

    text = " ".join(day_content).lower()

    # Wrong month: launch day says "april" when launch is March
    wrong_months = []
    for m in month_order:
        if m == expected_month:
            continue
        if m in text:
            wrong_months.append(m)
    if wrong_months and expected_idx >= 0:
        # Allow "march and april" or "through april" (range) but flag "opens april" style
        wrong_date_phrases = [
            r"opens?\s+(in\s+)?(" + "|".join(wrong_months) + r")",
            r"(" + "|".join(wrong_months) + r")\s+\d{1,2}",
            r"\d{1,2}\s+(" + "|".join(wrong_months) + r")",  # e.g. "4 April"
            r"(in|on)\s+(" + "|".join(wrong_months) + r")",
            r"mark\s+(your\s+)?calendars?\s+for\s+(" + "|".join(wrong_months) + r")",
        ]
        for pat in wrong_date_phrases:
            if re.search(pat, text):
                warnings.append(
                    f"Quality check: Launch day (Day {key_date_day}) may reference wrong month. "
                    f"Expected {expected_month}; found reference to {wrong_months}. "
                    f"Review CAPTION_QUALITY_STANDARDS.md and STORY_QUALITY_STANDARDS.md."
                )
                break
    return warnings


def _validate_story_quality(stories_md: str) -> list:
    """
    Post-generation validation for story output. Returns list of warning strings.
    Catches completeness issues (missing days, empty Idea/Suggested wording).
    Does not block delivery; caller may log warnings.
    """
    warnings = []
    if not stories_md or "**Day" not in stories_md:
        return warnings
    found_days = set()
    for m in re.finditer(r"\*\*Day\s+(\d+)\s*:\*\*\s*(.*?)(?=\s*\*\*Day\s+\d+\s*:\*\*|$)", stories_md, re.I | re.DOTALL):
        day_num = int(m.group(1))
        content = (m.group(2) or "").strip()
        if 1 <= day_num <= 30:
            found_days.add(day_num)
        if not content:
            warnings.append(f"Quality check: Story Day {day_num} has no content.")
            continue
        if "idea:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Idea.")
        if "suggested wording:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Suggested wording.")
        if "story hashtags:" not in content.lower() and "hashtags:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Story hashtags.")
    missing = set(range(1, 31)) - found_days
    if missing:
        warnings.append(f"Quality check: Story ideas missing days: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}.")
    return warnings


class CaptionGenerator:
    """Generate 30 captions from intake using AI. Uses 3 chunks to avoid timeouts and token limits."""

    CHUNKS = [(1, 10), (11, 20), (21, 30)]
    MAX_TOKENS_PER_CHUNK = 6000

    def __init__(self):
        provider = (Config.AI_PROVIDER or "openai").strip().lower()
        if provider == "anthropic":
            if not Config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured (set AI_PROVIDER=anthropic)")
        else:
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")

    def generate(self, intake: Dict[str, Any], previous_pack_themes: Optional[list] = None, pack_start_date: Optional[str] = None) -> str:
        """
        Generate full 30-day caption document as markdown in 3 API calls (days 1–10, 11–20, 21–30).
        If include_stories and platform has Instagram & Facebook, appends 30 Story prompts.
        previous_pack_themes: for subscriptions, list of previous packs' day categories.
        pack_start_date: YYYY-MM-DD so Day 1 = this date (default: today UTC). Ensures key-date phasing aligns.
        Raises on API error.
        """
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        include_hashtags = intake.get("include_hashtags", True)
        if isinstance(include_hashtags, str) and include_hashtags.lower() in ("false", "0", "no", "off"):
            include_hashtags = False
        system = _build_system_prompt(intake)
        header = _build_doc_header(intake, pack_start_date=start_str)
        parts = [header]
        for day_start, day_end in self.CHUNKS:
            user = _build_user_prompt(intake, day_start=day_start, day_end=day_end, previous_pack_themes=previous_pack_themes, pack_start_date=start_str)
            content = chat_completion(
                system=system,
                user=user,
                temperature=0.6,
                max_tokens=self.MAX_TOKENS_PER_CHUNK,
            )
            if not content:
                raise RuntimeError(f"AI returned empty content for days {day_start}-{day_end}")
            # Retry once if chunk has empty Caption/Hashtags blocks (incomplete output)
            if _chunk_has_empty_blocks(content, include_hashtags):
                retry_user = user + "\n\nIMPORTANT: Your previous response had empty Caption or Hashtags lines. You must fill every **Caption:** and every **Hashtags:** (when requested) with real, copy-paste-ready content for every platform for every day in this range. No exceptions."
                content = chat_completion(
                    system=system,
                    user=retry_user,
                    temperature=0.5,
                    max_tokens=self.MAX_TOKENS_PER_CHUNK,
                )
                if not content:
                    raise RuntimeError(f"AI returned empty content on retry for days {day_start}-{day_end}")
                if _chunk_has_empty_blocks(content, include_hashtags):
                    raise RuntimeError(f"AI still returned incomplete content for days {day_start}-{day_end} (empty Caption or Hashtags). Please try again.")
            parts.append(content)
        result = "\n".join(parts)

        # Stories add-on: when IG & FB selected and include_stories
        platform_raw = (intake.get("platform") or "").strip().lower()
        include_stories = bool(intake.get("include_stories"))
        align_stories = bool(intake.get("align_stories_to_captions"))
        has_ig_fb = "instagram" in platform_raw or "facebook" in platform_raw
        if include_stories and has_ig_fb:
            if align_stories:
                stories_md = self._generate_stories_aligned(
                    intake,
                    result,
                    is_subscription_variety=bool(previous_pack_themes),
                    pack_start_date=start_str,
                )
            else:
                stories_md = self._generate_stories(
                    intake,
                    is_subscription_variety=bool(previous_pack_themes),
                    pack_start_date=start_str,
                )
            if stories_md:
                result = result + "\n\n" + stories_md
                for w in _validate_story_quality(stories_md):
                    print(f"[CaptionGenerator] Story quality warning: {w}")

        # Post-generation validation: log quality warnings (does not block delivery)
        for w in _validate_caption_quality(result, intake, start_str):
            print(f"[CaptionGenerator] Quality warning: {w}")

        return result

    def _generate_stories(
        self,
        intake: Dict[str, Any],
        is_subscription_variety: bool = False,
        pack_start_date: Optional[str] = None,
    ) -> str:
        """Generate 30 one-line Story prompts for Instagram/Facebook.

        Stories use the SAME before/during/after key-date phasing as captions:
        pre-launch (days 1 to key_date-1), launch day (key_date), post-launch (key_date+1 to 30).
        KEY_DATE_EVENTS and day mapping must be passed when launch_event_description is set.
        """
        lang = (intake.get("caption_language") or "English (UK)").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
        n = _normalize_intake_case
        business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
        month_year = datetime.utcnow().strftime("%B %Y")
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        date_context = _build_date_context(start_str)
        date_block = ""
        if date_context:
            date_block = f"""

DATE_CONTEXT (their 30 days start on a specific date; use when relevant, e.g. weekday/weekend):
{date_context}

You may reference the actual day/date where it helps (e.g. Monday tip, weekend post). Use only when natural.
"""
        # Key date phasing: stories must align with launch/event dates (same as captions)
        key_date_block = ""
        launch_desc_raw = (intake.get("launch_event_description") or "").strip()
        launch_desc = n(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
        key_date_day = _parse_key_date_from_text(launch_desc_raw or launch_desc, start_str) if (launch_desc_raw or launch_desc) else None
        if launch_desc:
            key_date_block = f"""

KEY_DATE_EVENTS (user included dates in description):
{launch_desc}

Phase story content by the dates above: BEFORE = anticipation, teasers, countdown; ON/DURING = announce, promote; AFTER = thank-you, feedback. Do not put launch-day tone on the wrong day. Use the actual dates from DATE_CONTEXT when mentioning when events happen—do not invent different dates."""
            if key_date_day is not None:
                key_date_block += f"""

IMPORTANT — The client's key date above falls on Day {key_date_day}. Write pre-launch/anticipation stories for days 1 to {key_date_day - 1}, launch-day/announcement for Day {key_date_day}, and post-launch/thank-you for days {key_date_day + 1} to 30. Suggested wording must reference the correct dates (e.g. if launch is Day 7 = Fri 27 Mar, do not say "opens in April" on Day 7)."""
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"
        brand_rule = f"""
CRITICAL — Use ONLY this business name when naming the brand in Idea or Suggested wording: "{business}".
Do not invent, substitute, or use example/tagline business names from training (e.g. do not replace the real name with a slogan or another company). You may use "we" / "us" / "our" where natural; if the business name appears, it must be exactly "{business}".
Ground every suggestion in their intake (offer, audience, goal)—not generic industries from examples."""

        prompt = f"""Generate 30 Story prompts for Instagram/Facebook Stories. One per day (Day 1–30). Each day must have exactly three parts: Idea, Suggested wording, Story hashtags.

Quality bar: Every story set must be as tailored and specific as a premium content strategist would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Match the standard of a highly polished 30-day story plan.

{lang_instruction}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}
{date_block}
{key_date_block}
{variety_note}
{brand_rule}

For each day provide: (1) Idea — a short description of the Story concept (5–15 words). (2) Suggested wording: — one sentence or short suggestion for what to say or show (do not wrap in quotation marks). (3) Story hashtags: — 3–5 relevant hashtags. Mix types: behind-the-scenes, tips, questions, polls, product highlights, testimonials, process reveals, day-in-the-life. Variety is key.

Output format — markdown only, one line per day with all three parts on that line:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
**Day 2:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
...
**Day 30:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
---

Use the exact labels "Idea:", "Suggested wording:", and "Story hashtags:" on every line. Do not put quotation marks around the Suggested wording content. Output the complete list only. No preamble."""
        try:
            content = chat_completion(
                system=(
                    "You write concise Story prompts (Idea, Suggested wording, Story hashtags). "
                    "Quality bar: as tailored as a premium 30-day story plan. "
                    "Always respect INTAKE exactly: use only the client's real business name and offer—never fictional or example brands."
                ),
                user=prompt,
                temperature=0.7,
                max_tokens=3500,
            )
            return content if content else ""
        except Exception as e:
            print(f"[CaptionGenerator] Stories generation failed: {e}")
            return ""

    def _generate_stories_aligned(
        self,
        intake: Dict[str, Any],
        captions_md: str,
        is_subscription_variety: bool = False,
        pack_start_date: Optional[str] = None,
    ) -> str:
        """Generate 30 Story prompts with explicit day-by-day alignment to captions.

        Also receives KEY_DATE_EVENTS and before/during/after phasing (same as captions)
        so Suggested wording uses correct dates, not invented ones."""
        # Extract "## Day N — ..." headings to summarise each day's caption.
        day_summaries: Dict[int, str] = {}
        for line in captions_md.splitlines():
            m = re.match(r"^##\s*Day\s+(\d+)\s*[—\-]\s*(.+)$", line.strip())
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
                summary_lines.append(f"Day {i}: {day_summaries[i]}")

        summaries_block = "\n".join(summary_lines)

        lang = (intake.get("caption_language") or "English (UK)").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
        n = _normalize_intake_case
        business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
        month_year = datetime.utcnow().strftime("%B %Y")
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        date_context = _build_date_context(start_str)
        date_block = ""
        if date_context:
            date_block = f"""

DATE_CONTEXT (their 30 days start on a specific date; use when relevant):
{date_context}

You may reference the actual day/date where it helps. Use only when natural.
"""
        # Key date phasing: stories must align with launch/event dates (same as captions)
        key_date_block = ""
        launch_desc_raw = (intake.get("launch_event_description") or "").strip()
        launch_desc = n(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
        key_date_day = _parse_key_date_from_text(launch_desc_raw or launch_desc, start_str) if (launch_desc_raw or launch_desc) else None
        if launch_desc:
            key_date_block = f"""

KEY_DATE_EVENTS (user included dates in description):
{launch_desc}

Phase story content by the dates above. Use the actual dates from DATE_CONTEXT when mentioning when events happen—do not invent different dates."""
            if key_date_day is not None:
                key_date_block += f"""

IMPORTANT — The client's key date above falls on Day {key_date_day}. Suggested wording must reference the correct dates (e.g. if launch is Day 7 = Fri 27 Mar, do not say "opens in April" on Day 7)."""
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"

        brand_rule = f"""
CRITICAL — Use ONLY this business name when naming the brand in Idea or Suggested wording: "{business}".
Do not invent, substitute, or use example/tagline business names from training. If the business name appears, it must be exactly "{business}".
Ground every suggestion in their intake and that day's caption theme—not generic industries from examples."""

        prompt = f"""Generate 30 Story prompts for Instagram/Facebook Stories. One per day (Day 1–30). Each day must have exactly three parts: Idea, Suggested wording, Story hashtags.

Quality bar: Every story set must be as tailored and specific as a premium content strategist would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Each day's story must support that day's caption theme.

{lang_instruction}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}
{date_block}
{key_date_block}
{variety_note}
{brand_rule}

Here is the theme or focus for each day's main caption:
{summaries_block}

For each Day N, write a Story prompt that explicitly supports and reinforces that day's caption. Think of it as the visibility layer between posts: behind-the-scenes, polls, quick proof, or micro-examples that keep the message active.

For each day provide: (1) Idea: — short description of the Story concept (5–15 words). (2) Suggested wording: — one sentence or short suggestion for what to say or show (do not wrap in quotation marks). (3) Story hashtags: — 3–5 relevant hashtags. Mix types; variety is key, but always tied to that day's caption theme.

Output format — markdown only, one line per day with all three parts on that line:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
**Day 2:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
...
**Day 30:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
---

Use the exact labels "Idea:", "Suggested wording:", and "Story hashtags:" on every line. Do not put quotation marks around the Suggested wording content. Output the complete list only. No preamble."""

        try:
            content = chat_completion(
                system=(
                    "You write concise Story prompts aligned with an existing captions plan. "
                    "Quality bar: as tailored as a premium 30-day story plan. "
                    "Each day: Idea, Suggested wording, Story hashtags. Use only the client's real business name from INTAKE—never fictional brands."
                ),
                user=prompt,
                temperature=0.7,
                max_tokens=3500,
            )
            return content if content else ""
        except Exception as e:
            print(f"[CaptionGenerator] Aligned stories generation failed: {e}")
            return ""
