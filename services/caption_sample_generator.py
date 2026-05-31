"""
Generate a 3-caption snapshot for free sample orders (product_type = sample_3).
Separate from CaptionGenerator (30-day pack) to avoid coupling to pack size.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from services.ai_provider import chat_completion


def _brief_block(intake: Dict[str, Any]) -> str:
    lines = []
    for key, label in (
        ("business_name", "Business name"),
        ("business_type", "Business type"),
        ("offer_one_line", "Offer"),
        ("audience", "Audience"),
        ("audience_cares", "What audience cares about"),
        ("voice_words", "Voice / tone"),
        ("voice_avoid", "Avoid"),
        ("platform", "Platform"),
        ("goal", "Goal"),
        ("usual_topics", "Topics"),
        ("launch_event_description", "Key date / launch"),
        ("caption_language", "Language"),
    ):
        val = (intake.get(key) or "").strip()
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines) if lines else "(minimal brief)"


_PLATFORM_GUIDANCE = {
    "instagram & facebook": (
        "Instagram & Facebook (feed post). Open with a strong hook line, then keep the copy tight: "
        "usually 2–4 short sentences or a few short lines. Make it concrete enough that a stranger "
        "understands the offer; do not write a long essay unless the client's platform habits ask for it. "
        "End with a clear, low-pressure next step where natural."
    ),
    "linkedin": (
        "LinkedIn. Professional but human. Multiple sentences and depth are fine — usually 2–6 "
        "short paragraphs when appropriate. Open with a hook line, then insight, story, or specifics "
        "relevant to the audience. End with a question or soft CTA."
    ),
    "tiktok": (
        "TikTok caption. 1–3 short lines. Hook in the first line, clear CTA, conversational. "
        "Use fewer hashtags than Instagram and TikTok-appropriate tag style."
    ),
    "pinterest": (
        "Pinterest pin. Search-friendly, keyword-rich description with a clear title and a clear "
        "description that includes relevant keywords and a CTA / link cue where appropriate. Focus "
        "on what the pin shows and who it helps."
    ),
}


def _platform_guidance(platform: str) -> str:
    p = (platform or "").strip().lower()
    if not p:
        return _PLATFORM_GUIDANCE["instagram & facebook"]
    if "instagram" in p or "facebook" in p:
        return _PLATFORM_GUIDANCE["instagram & facebook"]
    if "linkedin" in p:
        return _PLATFORM_GUIDANCE["linkedin"]
    if "tiktok" in p:
        return _PLATFORM_GUIDANCE["tiktok"]
    if "pinterest" in p:
        return _PLATFORM_GUIDANCE["pinterest"]
    return _PLATFORM_GUIDANCE["instagram & facebook"]


def generate_sample_captions(intake: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (captions_md, error_message). captions_md is markdown for email + DB storage.
    """
    brief = _brief_block(intake)
    lang = (intake.get("caption_language") or "English (UK)").strip() or "English (UK)"
    platform = (intake.get("platform") or "Instagram & Facebook").strip() or "Instagram & Facebook"
    platform_rules = _platform_guidance(platform)
    system = (
        "You write ready-to-post social media captions for local businesses, tailored to each "
        "platform's conventions and length norms. "
        "Default tone (used only when the client has not specified otherwise): "
        "confident, editorial, modern, premium; smart, human, intelligent; "
        "no emojis; no buzzwords or marketing clichés; avoid hype and generic AI language. "
        "**The client's intake takes priority over these defaults.** "
        "When the brief lists a Voice / tone to use, write in that voice — even if it means using "
        "emojis, playful language, or other things the default would avoid. "
        "When the brief lists Words / style to avoid, never use them. "
        "Output valid JSON only, no markdown fences."
    )
    tiktok_hashtags = "TikTok: 3–5 platform-appropriate hashtags."
    linkedin_hashtags = "LinkedIn: 2–4 hashtags."
    instagram_hashtags = "Instagram & Facebook: 3–8 relevant hashtags."
    pinterest_hashtags = "Pinterest: 3–6 keyword-led hashtags."
    user = f"""Write exactly 3 social media captions for this business (Days 1–3 of a sample pack).

Target platform: {platform}
Language: {lang}
Use UK spelling when language is English (UK).

Platform-specific length and style:
{platform_rules}

Return JSON:
{{
  "captions": [
    {{"day": 1, "category": "short label e.g. Welcome", "caption": "full caption text", "hashtags": "#tag1 #tag2"}},
    {{"day": 2, "category": "...", "caption": "...", "hashtags": "..."}},
    {{"day": 3, "category": "...", "caption": "...", "hashtags": "..."}}
  ]
}}

Rules:
- Vary the angle across the 3 days (e.g. welcome / story / value tip / behind-the-scenes / member spotlight / clear CTA). Do not repeat the same structure each day.
- Conversational, specific to the business — reference real details from the brief.
- The client's intake (Voice / tone, Words / style to avoid, Goal, Audience, etc.) is authoritative — match it precisely. Their voice overrides the default house style above.
- When the client's goal is leads or inquiries, include a clear, low-pressure next step (e.g. link in bio, DM, book a call) where it fits naturally — never pushy. If the intake describes a different goal or CTA style, follow that instead.
- Hashtags by platform: {instagram_hashtags} {linkedin_hashtags} {tiktok_hashtags} {pinterest_hashtags}
- No invented prices, dates, or claims not supported by the brief.
- Do not mention this is a sample or free trial.

Business brief:
{brief}
"""
    try:
        raw = chat_completion(system=system, user=user, temperature=0.7, max_tokens=4000)
    except Exception as e:
        return None, f"AI generation failed: {e}"

    captions = _parse_captions_json(raw)
    if not captions:
        return None, "Could not parse AI response"

    md_lines: list[str] = []
    for idx, item in enumerate(captions[:3], start=1):
        day = item.get("day") or idx
        cat = (item.get("category") or "Caption").strip()
        cap = (item.get("caption") or "").strip()
        tags = (item.get("hashtags") or "").strip()
        md_lines.append(f"Day {day} — {cat}")
        md_lines.append("")
        md_lines.append(cap)
        if tags:
            md_lines.append("")
            md_lines.append(tags)
        md_lines.append("")
    return "\n".join(md_lines).strip(), None


def _parse_captions_json(raw: str) -> Optional[list]:
    text = (raw or "").strip()
    if not text:
        return None
    # Strip optional ```json fence
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find first { ... }
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    caps = data.get("captions") if isinstance(data, dict) else None
    if isinstance(caps, list) and caps:
        return caps
    return None
