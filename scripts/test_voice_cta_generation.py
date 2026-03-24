#!/usr/bin/env python3
"""
Test that caption generation uses voice_words, voice_avoid, and goal-driven CTA.
1. Prints system + user prompt (chunk 1) to confirm voice/CTA instructions are present.
2. Runs one API chunk (days 1–10) and checks the first caption for voice fit and CTA.

Usage (from repo root):
  python3 scripts/test_voice_cta_generation.py          # prompt check only (no API)
  python3 scripts/test_voice_cta_generation.py --live   # run one chunk and check output

Requires .env with OPENAI_API_KEY or ANTHROPIC_API_KEY (for --live).
"""
import os
import re
import sys

# Run from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()

def _today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_intake():
    """Intake with explicit voice and goal so we can verify prompt and output."""
    return {
        "business_name": "Test Bakery",
        "business_type": "Product brand / E-commerce",
        "offer_one_line": "We make celebration cakes and brownies for local delivery.",
        "audience": "Consumers, Small business owners",
        "consumer_age_range": "25-45",
        "audience_cares": "quality ingredients, special occasions, supporting local",
        "voice_words": "warm, friendly, concise",
        "voice_avoid": "jargon, hype, overly formal",
        "platform": "Instagram & Facebook",
        "platform_habits": "shorter on Instagram",
        "goal": "More inquiries / leads",
        "caption_language": "English (UK)",
        "include_hashtags": True,
        "hashtag_min": 3,
        "hashtag_max": 8,
        "launch_event_description": "",
        "caption_examples": "",
    }


def main():
    from services.caption_generator import (
        _build_system_prompt,
        _build_user_prompt,
        _build_doc_header,
    )

    intake = test_intake()
    do_live = "--live" in sys.argv

    print("=" * 60)
    print("1. PROMPT CHECK (voice + CTA instructions)")
    print("=" * 60)

    system = _build_system_prompt(intake)
    user = _build_user_prompt(intake, day_start=1, day_end=10, pack_start_date=_today_utc())

    # Check system prompt
    has_voice_override = "Voice / tone to use" in system or "prioritise those" in system or "override the default" in system
    print("\n[System prompt] Client voice override mentioned:", has_voice_override)
    if not has_voice_override:
        print("  WARNING: Expected system to say client voice/avoid override default tone.")
    else:
        print("  OK")

    # Check user prompt
    has_voice_intake = "Voice / tone to use" in user and "warm, friendly, concise" in user
    has_avoid_intake = "Words / style to avoid" in user and "jargon, hype" in user
    has_voice_instruction = "VOICE:" in user and "Match the client" in user
    has_cta_instruction = "next step" in user.lower() and ("leads" in user or "inquiries" in user)
    print("\n[User prompt] Voice in INTAKE:", has_voice_intake)
    print("[User prompt] Avoid in INTAKE:", has_avoid_intake)
    print("[User prompt] VOICE instruction line:", has_voice_instruction)
    print("[User prompt] CTA / next step for leads:", has_cta_instruction)
    if not (has_voice_intake and has_voice_instruction):
        print("  WARNING: Voice should appear in INTAKE and VOICE instruction.")
    if not has_cta_instruction:
        print("  WARNING: Goal is 'More inquiries / leads'; expected CTA/next-step hint.")

    # Show relevant snippets
    print("\n--- System (tone line only) ---")
    for line in system.splitlines():
        if "Tone:" in line or "voice" in line.lower():
            print(line[:120] + ("..." if len(line) > 120 else ""))
    print("\n--- User INTAKE (voice + goal) ---")
    for line in user.splitlines():
        if "Voice" in line or "avoid" in line.lower() or "Goal" in line or "VOICE:" in line:
            print(line[:120] + ("..." if len(line) > 120 else ""))

    if not do_live:
        print("\n" + "=" * 60)
        print("Run with --live to call the API and check one caption for voice/CTA.")
        print("=" * 60)
        return

    print("\n" + "=" * 60)
    print("2. LIVE RUN (one chunk: days 1–10)")
    print("=" * 60)

    from config import Config
    from services.ai_provider import chat_completion as ai_chat

    provider = (getattr(Config, "AI_PROVIDER", None) or "openai").strip().lower()
    if provider == "anthropic" and not getattr(Config, "ANTHROPIC_API_KEY", None):
        print("ANTHROPIC_API_KEY not set. Skipping live run.")
        return
    if provider != "anthropic" and not getattr(Config, "OPENAI_API_KEY", None):
        print("OPENAI_API_KEY not set. Skipping live run.")
        return

    header = _build_doc_header(intake, pack_start_date=_today_utc())
    content = ai_chat(system=system, user=user, temperature=0.6, max_tokens=6000)
    if not content:
        print("API returned empty content.")
        return

    full_chunk = content
    # Find first **Caption:** block (may be \n\n after label)
    caption_blocks = re.findall(
        r"\*\*Caption:\*\*\s*\n+\s*(.*?)(?=\n\s*\*\*|\n\s*---|\n##\s*Day\s|\Z)",
        full_chunk,
        re.DOTALL,
    )
    first_caption = (caption_blocks[0].strip() if caption_blocks else "")[:1000]
    if not first_caption:
        # Fallback: show raw start so we can see structure
        first_caption = full_chunk[:1200]

    print("\nFirst caption (snippet):")
    print("-" * 40)
    print(first_caption or "(no caption block found)")
    print("-" * 40)

    # Heuristic checks
    voice_ok = any(w in first_caption.lower() for w in ["warm", "friendly", "we ", "our "])
    no_hype = "hype" not in first_caption.lower() and "jargon" not in first_caption.lower()
    cta_ok = any(
        phrase in first_caption.lower()
        for phrase in ["link in bio", "dm", "message us", "get in touch", "order", "book", "comment", "link below", "in our bio"]
    )
    print("\n[Output check] Tone feels warm/friendly or on-brand:", voice_ok)
    print("[Output check] No obvious hype/jargon:", no_hype)
    print("[Output check] Clear next step (CTA) present:", cta_ok)
    if cta_ok:
        print("  CTA behaviour: OK (caption includes a next step).")
    else:
        print("  Note: CTA may appear in later captions or Soft Promotion days.")


if __name__ == "__main__":
    main()
