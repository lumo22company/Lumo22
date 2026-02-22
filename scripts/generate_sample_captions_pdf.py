#!/usr/bin/env python3
"""
Generate a sample 30 Days Captions PDF so you can preview the branded document.
Run: python3 scripts/generate_sample_captions_pdf.py
Output: sample_30_days_captions.pdf (in project root)
"""
import os
import sys

# Add project root so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_pdf import build_caption_pdf, get_logo_path

SAMPLE_MD = """# 30 Days of Social Media Captions
Acme Strategy | March 2025

---
INTAKE SUMMARY
---
- Business: Strategy consultancy for scaling founders.
- Audience: Founders and operators, 5–50 employees.
- Voice: Direct, calm, precise, no hype.
- Platform: LinkedIn, Instagram.
- Goal: More qualified discovery calls this month.

---
CAPTIONS
---

## Day 1 — Authority / Expertise
**Platform:** LinkedIn
**Caption:** Most people treat strategy as a one-off event.

Most people treat strategy as a one-off event. You book a workshop, you leave with a deck, and then it sits in a drawer. The reality is that strategy only works when it's tied to how you actually make decisions—who's in the room, what you measure, and how often you revisit it. That's why we focus on decision rhythm first, and the document second.

**Hashtags:** #Strategy #Leadership #Founders

**Platform:** Instagram
**Caption:** Strategy isn't a one-day workshop.

Strategy isn't a one-day workshop. It's a rhythm: who decides, what you measure, how often you revisit. We focus on decision habits first—then the document. Less deck, more discipline.

**Hashtags:** #Strategy #Leadership #BusinessStrategy

---
## Day 2 — Educational / Value
**Platform:** LinkedIn
**Caption:** Here's how to run a quarterly review without it turning into a status dump.

Here's how to run a quarterly review without it turning into a status dump.

One: Set the question in advance. "What did we learn?" beats "What did we do?"
Two: Limit the deck. If it's more than a few slides, it's not a review, it's a report.
Three: End with one decision. One thing you're changing next quarter because of what you learned.

Do that, and the meeting earns its place on the calendar.

**Hashtags:** #Leadership #QuarterlyReview #Strategy

**Platform:** Instagram
**Caption:** Three questions for a better quarterly review.

What did we learn? What changed? One decision for next quarter. Keep it simple.

**Hashtags:** #QuarterlyReview #Leadership #TeamWork

---
## Day 3 — Brand Personality
**Platform:** LinkedIn
**Caption:** I don't do "strategy weekends."

I don't do "strategy weekends." Nothing that matters gets decided in two days of sticky notes. Instead we work in short cycles: a few hours of focus, then a week of living with the draft, then another pass. It takes longer on the calendar but the decisions stick because they've been tested against real work.

That's the trade we ask clients to make. Less theatre, more iteration.

**Hashtags:** #Strategy #Process #Iteration

---
## Day 4 — Soft Promotion
**Platform:** LinkedIn
**Caption:** If you're leading a team of 10–30 and your "strategy" is still a PDF from last year, this is for you.

If you're leading a team of 10–30 and your "strategy" is still a PDF from last year, this is for you. We help you turn it into a running discipline: clear priorities, a simple rhythm, and one place everyone looks for what matters. No big consultancy process, no offsites that don't stick.

Discovery calls are open for April. Link in my profile.

**Hashtags:** #Strategy #Scaling #DiscoveryCalls

---
## Day 5 — Engagement
**Platform:** LinkedIn
**Caption:** This week I'm thinking about what "strategy" actually means when you're in the middle of scaling.

This week I'm thinking about what "strategy" actually means when you're in the middle of scaling. Is it the plan, or is it the habit of deciding what to do next with the information you have? I lean toward the second. What would you add?

**Hashtags:** #Strategy #Scaling #Leadership

---
*[Days 6–30 follow the same format in the full document.]*
"""

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, "sample_30_days_captions.pdf")
    logo_path = get_logo_path()
    if not logo_path:
        logo_path = os.path.join(root, "static", "images", "logo.png")
        if not os.path.isfile(logo_path):
            logo_path = None
    pdf_bytes = build_caption_pdf(SAMPLE_MD, logo_path=logo_path)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Sample PDF written to: {out_path}")
    print("Open it to preview the branded captions document customers receive.")

if __name__ == "__main__":
    main()
