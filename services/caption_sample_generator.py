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
        "Instagram & Facebook (feed post). Open with a strong hook line, then 3–6 short paragraphs "
        "of storytelling, value, or specifics. Add a clear call to action at the end. "
        "Aim for ~120–220 words. Use line breaks between paragraphs for scannability."
    ),
    "linkedin": (
        "LinkedIn. Professional but human. Open with a hook line, then 4–7 short paragraphs of "
        "insight, story, or specifics relevant to the audience. End with a question or soft CTA. "
        "Aim for ~150–280 words. Avoid emojis."
    ),
    "tiktok": (
        "TikTok caption. 1–3 short lines maximum. Hook-led, punchy, conversational. "
        "Aim for under 150 characters. Hashtags carry weight here — use trending and niche tags."
    ),
    "pinterest": (
        "Pinterest pin description. 1–2 sentences, keyword-rich, descriptive. "
        "Aim for ~100–200 characters. Focus on what the pin shows and who it helps."
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
        "platform's conventions and length norms. Output valid JSON only, no markdown fences."
    )
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
- Hashtags: 3–8 relevant tags as one string. For LinkedIn keep to 2–4. For TikTok and Pinterest 4–8 trending and niche tags work well.
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
