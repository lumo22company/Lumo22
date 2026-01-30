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

Tone: confident, editorial, modern, premium. No emojis. No buzzwords or marketing clichés. Calm, human, intelligent. Avoid hype and generic AI language.

You produce a 30-day caption plan using exactly these five categories, distributed across the month:
- Authority / Expertise (establish credibility, perspective, experience)
- Educational / Value (teach something useful, answer a real question)
- Brand Personality (process, philosophy, behind-the-scenes)
- Soft Promotion (invite a next step, mention offer, low pressure)
- Engagement (questions, prompts, conversation starters)

Output format: You must respond with a single markdown document. Structure:
1. Title: "# 30 Days of Social Media Captions"
2. Subtitle: "[Client name or business] | [Current month year]"
3. Section "---" then "INTAKE SUMMARY" then "---" then 5 bullet lines: Business, Audience, Voice, Platform, Goal (from the intake).
4. Section "---" then "CAPTIONS" then "---"
5. For each day (1–30): "## Day N — [Category]" then "**Platform:** [e.g. LinkedIn / Instagram]" then "**Suggested hook:** [first line of caption]" then a blank line then the full caption text (ready to copy-paste). Then "---".

Write 30 distinct captions. Rotate through the five categories so the mix feels balanced (roughly 6 of each). Every caption must be tailored to the client's business, audience, voice, platform, and goal. No placeholder text. No "[insert X]". Each caption should be 2–6 short paragraphs, copy-paste ready."""


def _build_user_prompt(intake: Dict[str, Any]) -> str:
    from datetime import datetime
    month_year = datetime.utcnow().strftime("%B %Y")
    parts = [
        f"Generate the full 30-day caption document for this client. Current month/year: {month_year}.",
        "",
        "INTAKE:",
        f"- Business type: {intake.get('business_type', '')}",
        f"- What they offer (one sentence): {intake.get('offer_one_line', '')}",
        f"- Primary audience: {intake.get('audience', '')}",
        f"- What audience cares about: {intake.get('audience_cares', '')}",
        f"- Voice (3–5 words): {intake.get('voice_words', '')}",
        f"- Language to avoid: {intake.get('voice_avoid', '') or 'None specified'}",
        f"- Primary platform: {intake.get('platform', '')}",
        f"- Platform habits: {intake.get('platform_habits', '') or 'None'}",
        f"- Goal for the month: {intake.get('goal', '')}",
        "",
        "Output the complete markdown document only. No preamble or explanation."
    ]
    return "\n".join(parts)


class CaptionGenerator:
    """Generate 30 captions from intake using OpenAI."""

    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL

    def generate(self, intake: Dict[str, Any]) -> str:
        """
        Generate full 30-day caption document as markdown.
        Raises on API error.
        """
        system = _build_system_prompt()
        user = _build_user_prompt(intake)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            max_tokens=16000,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("OpenAI returned empty caption document")
        return content.strip()
