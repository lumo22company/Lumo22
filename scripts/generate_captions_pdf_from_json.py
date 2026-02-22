#!/usr/bin/env python3
"""
Generate a 30 Days Captions PDF from JSON input — matches reference style exactly.
Run: python3 scripts/generate_captions_pdf_from_json.py [input.json]
  or with no args, uses built-in sample data.

Output: 30_Days_Social_Media_Captions_[Month_Year].pdf (e.g. FEBRUARY_2026)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_pdf import build_caption_pdf_from_dict, get_logo_path, generate_filename

SAMPLE_DATA = {
    "month_year": "FEBRUARY 2026",
    "business": "test",
    "audience": "Consumers",
    "voice": "direct, thoughtful, professional, playful, inspiring",
    "platforms": "Instagram & Facebook, LinkedIn",
    "goal": "Grow following",
    "days": [
        {
            "day": 1,
            "theme": "AUTHORITY / EXPERTISE",
            "posts": [
                {
                    "platform": "Instagram & Facebook",
                    "caption": "Confidence comes from knowledge. In the world of coaching, experience is paramount. At test, I draw on years of helping individuals transform their lives. Each training programme is tailored to inspire and empower you to reclaim your confidence.",
                    "hashtags": "#ConfidenceCoach #PersonalGrowth #FatAcceptance #BodyPositivity #Empowerment"
                },
                {
                    "platform": "LinkedIn",
                    "caption": "Confidence comes from knowledge. In coaching, experience is paramount. I draw on years of helping individuals transform their lives. Each programme is tailored to inspire and empower. Your journey is unique—I'm here to guide you.",
                    "hashtags": "#ConfidenceCoach #PersonalGrowth #Leadership #Coaching"
                }
            ]
        },
        {
            "day": 2,
            "theme": "AUTHORITY / EXPERTISE",
            "posts": [
                {
                    "platform": "Instagram & Facebook",
                    "caption": "Confidence comes from knowledge. In the world of coaching, experience is paramount.",
                    "hashtags": "#ConfidenceCoach #PersonalGrowth"
                }
            ]
        },
        {
            "day": 3,
            "theme": "EDUCATIONAL / VALUE",
            "posts": [
                {
                    "platform": "LinkedIn",
                    "caption": "Here's how to run a quarterly review without it turning into a status dump.",
                    "hashtags": "#Leadership #QuarterlyReview"
                }
            ]
        },
        {"day": 4, "theme": "BRAND PERSONALITY", "posts": [{"platform": "Instagram", "caption": "I don't do strategy weekends.", "hashtags": "#Strategy"}]},
        {"day": 5, "theme": "SOFT PROMOTION", "posts": [{"platform": "LinkedIn", "caption": "Discovery calls are open for April.", "hashtags": "#Discovery"}]},
        {"day": 6, "theme": "ENGAGEMENT", "posts": [{"platform": "Instagram", "caption": "What would you add?", "hashtags": "#Engagement"}]},
        {"day": 7, "theme": "AUTHORITY", "posts": [{"platform": "Facebook", "caption": "Experience is paramount.", "hashtags": "#Expert"}]},
        {"day": 8, "theme": "VALUE", "posts": [{"platform": "LinkedIn", "caption": "One thing you're changing next quarter.", "hashtags": "#Strategy"}]},
        {"day": 9, "theme": "PERSONALITY", "posts": [{"platform": "Instagram", "caption": "Less theatre, more iteration.", "hashtags": "#Iteration"}]},
        {"day": 10, "theme": "PROMOTION", "posts": [{"platform": "LinkedIn", "caption": "Link in my profile.", "hashtags": "#Discovery"}]},
    ]
}


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            data = json.load(f)
    else:
        data = SAMPLE_DATA

    logo_path = get_logo_path()
    pdf_bytes = build_caption_pdf_from_dict(data, logo_path)
    out_name = generate_filename(data.get("month_year", "Captions"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, out_name)

    with open(out_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"PDF written to: {out_path}")


if __name__ == "__main__":
    main()
