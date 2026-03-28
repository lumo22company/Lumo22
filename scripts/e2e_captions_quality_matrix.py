#!/usr/bin/env python3
"""
Generate caption + story PDFs for several distinct business intakes (same pipeline as production).

Use this to review PDF quality without going through Stripe. For payment E2E, see
scripts/e2e_stripe_flows_checklist.txt (manual steps while signed in with Stripe test mode).

Usage:
  python3 scripts/e2e_captions_quality_matrix.py
  python3 scripts/e2e_captions_quality_matrix.py --only northwind_plant
  python3 scripts/e2e_captions_quality_matrix.py --dry-run
  python3 scripts/e2e_captions_quality_matrix.py --print-flows

Requires: .env with OPENAI_API_KEY or ANTHROPIC_API_KEY (no SendGrid/Supabase needed for PDF-only).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Fixed pack start so DATE_CONTEXT is stable across runs (edit if you want different dates)
PACK_START = "2026-03-28"

# Distinct verticals + platform / event mix for quality review
BUSINESS_FIXTURES: list[dict] = [
    {
        "slug": "northwind_plant",
        "intake": {
            "business_name": "Northwind Plant Lab",
            "business_type": "Rare plant nursery / online shop",
            "offer_one_line": "Curated rare plants with lab-grade care guidance.",
            "audience": "Serious collectors and design-minded plant people",
            "audience_cares": "Provenance, health, and rare drops",
            "voice_words": "warm, precise, quietly excited",
            "voice_avoid": "hypey sales tone",
            "platform": "Instagram & Facebook",
            "platform_habits": "Reels, carousels, Stories",
            "goal": "Drive traffic to the rare-drop preview weekend",
            "caption_examples": "",
            "include_stories": True,
            "align_stories_to_captions": True,
            "launch_event_description": "Spring rare-drop preview 12–13 April (online)",
        },
    },
    {
        "slug": "harbor_coffee",
        "intake": {
            "business_name": "Harbor Coffee Roasters",
            "business_type": "Specialty coffee roastery and café",
            "offer_one_line": "Small-batch roasted beans and weekday brunch in a harbour-side café.",
            "audience": "Local professionals and weekend visitors",
            "audience_cares": "Taste, freshness, and a calm place to sit",
            "voice_words": "friendly, sensory, unpretentious",
            "voice_avoid": "corporate jargon",
            "platform": "Instagram & Facebook",
            "platform_habits": "Reels, latte art, behind the bar",
            "goal": "More weekday breakfast visits and bean subscriptions",
            "caption_examples": "",
            "include_stories": True,
            "align_stories_to_captions": True,
            "launch_event_description": "",
        },
    },
    {
        "slug": "summit_strategy",
        "intake": {
            "business_name": "Summit Strategy Partners",
            "business_type": "B2B strategy consultancy",
            "offer_one_line": "We help leadership teams align on strategy and execution in 90-day sprints.",
            "audience": "COOs and heads of ops at 50–500 employee firms",
            "audience_cares": "Clarity, accountability, and measurable outcomes",
            "voice_words": "direct, evidence-led, calm",
            "voice_avoid": "hype, buzzwords",
            "platform": "LinkedIn, Instagram",
            "platform_habits": "Long-form LinkedIn; short IG for culture",
            "goal": "Booked discovery calls from LinkedIn",
            "caption_examples": "",
            "include_stories": True,
            "align_stories_to_captions": True,
            "launch_event_description": "",
        },
    },
    {
        "slug": "ember_fitness",
        "intake": {
            "business_name": "Ember Coaching",
            "business_type": "Online strength and conditioning coach",
            "offer_one_line": "Programmes for busy runners who want strength without gym overwhelm.",
            "audience": "Amateur runners 30–50",
            "audience_cares": "Injury prevention, consistency, time-efficient sessions",
            "voice_words": "encouraging, no-nonsense, science-aware",
            "voice_avoid": "shame-based motivation",
            "platform": "Instagram, TikTok",
            "platform_habits": "Short form tips, form checks, client wins",
            "goal": "Waitlist sign-ups for next cohort",
            "caption_examples": "",
            "include_stories": True,
            "align_stories_to_captions": True,
            "launch_event_description": "Spring cohort opens 5 May",
        },
    },
    {
        "slug": "lumen_home",
        "intake": {
            "business_name": "Lumen Home",
            "business_type": "Independent homeware and lighting shop",
            "offer_one_line": "Thoughtfully sourced lighting and homeware with a focus on natural materials.",
            "audience": "Homeowners renovating and design lovers",
            "audience_cares": "Quality, longevity, and how pieces feel in a room",
            "voice_words": "warm, editorial, tactile",
            "voice_avoid": "pushy sales",
            "platform": "Instagram & Facebook, Pinterest",
            "platform_habits": "Room shots, Pinterest SEO, seasonal stories",
            "goal": "Online orders and showroom appointments",
            "caption_examples": "",
            "include_stories": True,
            "align_stories_to_captions": True,
            "launch_event_description": "",
        },
    },
]


def _print_stripe_flows(base: str) -> None:
    base = (base or "").strip().rstrip("/")
    if not base.startswith("http"):
        base = "https://www.lumo22.com"
    print("Stripe test mode: use card 4242 4242 4242 4242, any future expiry, any CVC.")
    print("Sign in first where the flow says [account required].")
    print()
    flows = [
        ("One-off · GBP · 1 platform · no stories", f"{base}/captions-checkout?platforms=1&currency=gbp"),
        ("One-off · GBP · 1 platform · + Story Ideas", f"{base}/captions-checkout?platforms=1&currency=gbp&stories=1"),
        ("One-off · GBP · 2 platforms (pick 2 in /captions) · + stories", f"{base}/captions-checkout?platforms=2&currency=gbp&stories=1"),
        ("One-off · USD · 1 platform", f"{base}/captions-checkout?platforms=1&currency=usd"),
        ("One-off · EUR · 1 platform + stories", f"{base}/captions-checkout?platforms=1&currency=eur&stories=1"),
        ("Subscription · GBP · 1 platform [account required]", f"{base}/captions-checkout-subscription?platforms=1&currency=gbp"),
        ("Subscription · GBP · + stories [account required]", f"{base}/captions-checkout-subscription?platforms=1&currency=gbp&stories=1"),
        ("Upgrade from one-off (after delivery) [account required]", f"{base}/captions-checkout-subscription?copy_from=YOUR_ORDER_TOKEN&platforms=1&currency=gbp"),
    ]
    for title, url in flows:
        print(f"• {title}")
        print(f"  {url}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E-style caption/story PDF quality matrix")
    parser.add_argument("--only", type=str, default="", help="Single fixture slug (e.g. northwind_plant)")
    parser.add_argument("--dry-run", action="store_true", help="List fixtures only")
    parser.add_argument("--print-flows", action="store_true", help="Print Stripe test-mode checkout URLs and exit")
    args = parser.parse_args()

    if args.print_flows:
        from config import Config

        _print_stripe_flows(Config.BASE_URL or "")
        return

    fixtures = BUSINESS_FIXTURES
    if args.only:
        fixtures = [f for f in BUSINESS_FIXTURES if f["slug"] == args.only]
        if not fixtures:
            print(f"Unknown slug: {args.only}", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        for f in fixtures:
            print(f["slug"])
        return

    from config import Config
    from services.caption_generator import CaptionGenerator
    from services.caption_pdf import build_caption_pdf, build_stories_pdf, get_logo_path

    provider = (getattr(Config, "AI_PROVIDER", None) or "openai").strip().lower()
    if provider == "anthropic" and not getattr(Config, "ANTHROPIC_API_KEY", None):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if provider != "anthropic" and not getattr(Config, "OPENAI_API_KEY", None):
        print("ERROR: OPENAI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.join(_ROOT, "e2e_output")
    os.makedirs(out_dir, exist_ok=True)

    gen = CaptionGenerator()
    logo_path = get_logo_path()
    index_lines = [
        f"# E2E PDF samples generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Pack start date: {PACK_START}",
        "",
    ]

    for fx in fixtures:
        slug = fx["slug"]
        intake = fx["intake"]
        print(f"\n=== {slug} ===")
        print("Generating (may take several minutes)...")
        captions_md = gen.generate(intake, pack_start_date=PACK_START)
        cap_path = os.path.join(out_dir, f"{slug}_captions.pdf")
        md_path = os.path.join(out_dir, f"{slug}_captions.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(captions_md)
        pdf_c = build_caption_pdf(captions_md, logo_path=logo_path, pack_start_date=PACK_START)
        with open(cap_path, "wb") as f:
            f.write(pdf_c)
        print(f"  Wrote {cap_path}")

        stories_pdf = build_stories_pdf(captions_md, logo_path=logo_path, pack_start_date=PACK_START)
        if stories_pdf:
            sp = os.path.join(out_dir, f"{slug}_stories.pdf")
            with open(sp, "wb") as f:
                f.write(stories_pdf)
            print(f"  Wrote {sp}")
        else:
            print("  (No stories PDF — check platform includes Instagram/Facebook for Story Ideas)")

        index_lines.append(f"- **{slug}**: `{os.path.basename(cap_path)}`, `{os.path.basename(md_path)}`" + (f", `{slug}_stories.pdf`" if stories_pdf else ""))

    readme = os.path.join(out_dir, "INDEX.txt")
    with open(readme, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines) + "\n")
    print(f"\nDone. Open {out_dir} and review PDFs.")
    print("For Stripe payment E2E: python3 scripts/e2e_captions_quality_matrix.py --print-flows")


if __name__ == "__main__":
    main()
