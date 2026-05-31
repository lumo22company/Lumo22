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


def generate_sample_captions(intake: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (captions_md, error_message). captions_md is markdown for email + DB storage.
    """
    brief = _brief_block(intake)
    lang = (intake.get("caption_language") or "English (UK)").strip() or "English (UK)"
    system = (
        "You write short, ready-to-post social media captions for local businesses. "
        "Output valid JSON only, no markdown fences."
    )
    user = f"""Write exactly 3 social media captions for this business (Days 1–3 of a sample pack).

Language: {lang}
Use UK spelling when language is English (UK).

Return JSON:
{{
  "captions": [
    {{"day": 1, "category": "short label e.g. Welcome", "caption": "full caption text", "hashtags": "#tag1 #tag2"}},
    {{"day": 2, "category": "...", "caption": "...", "hashtags": "..."}},
    {{"day": 3, "category": "...", "caption": "...", "hashtags": "..."}}
  ]
}}

Rules:
- Each caption 2–4 short paragraphs or lines; conversational, specific to the business.
- Hashtags: 3–8 relevant tags as one string.
- No invented prices, dates, or claims not supported by the brief.
- Do not mention this is a sample or free trial.

Business brief:
{brief}
"""
    try:
        raw = chat_completion(system=system, user=user, temperature=0.65, max_tokens=2500)
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
        md_lines.append(f"## Day {day} — {cat}")
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
