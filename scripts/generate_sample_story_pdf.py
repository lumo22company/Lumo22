#!/usr/bin/env python3
"""
Generate a sample 30 Days Story Ideas PDF so you can preview the branded document.
Run: python3 scripts/generate_sample_story_pdf.py
Output: sample_30_days_story_ideas.pdf (in project root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.caption_pdf import build_stories_pdf, get_logo_path

SAMPLE_MD = """# Stories Visibility Pack — 30 Days of Story Ideas
Acme Strategy | March 2025

---
INTAKE SUMMARY
---
- Business: Strategy consultancy for scaling founders.
- Audience: Founders and operators, 5–50 employees.
- Voice: Direct, calm, precise, no hype.
- Platform: Instagram & Facebook.
- Goal: More qualified discovery calls this month.

---
## 30 Story Ideas | Acme Strategy | March 2025

**Day 1:** Daily Story prompt aligned to todays client result caption. Suggested wording: Behind-the-scenes or a testimonial snippet that reinforces the post. Story hashtags: #clientresult #socialproof #strategy #stories
**Day 2:** Story prompt that keeps you visible between posts. Suggested wording: Which of these slows you down most right now? Offer 2–3 options in a poll. Story hashtags: #poll #founders #businessgrowth
**Day 3:** Support todays authority post with a day in the life Story. Suggested wording: What strategy work looks like behind the scenes. Story hashtags: #behindthescenes #consultantlife #visibility
**Day 4:** When the feed post is a soft promotion, use Stories to lower the barrier. Suggested wording: Three things clients ask before booking a call plus a question sticker. Story hashtags: #offer #qanda #clientquestions
**Day 5:** On engagement days, Stories can deepen the conversation. Suggested wording: What would make strategy feel easier for you this month? Story hashtags: #engagement #storyprompt #businesschat
**Day 6:** Align with a how-to post by showing a micro-step in Stories. Suggested wording: Step 1: Name the decision. Step 2: Name who decides. Story hashtags: #howto #process #stories
**Day 7:** When you share a client story in the feed, use Stories for a quick before/after. Suggested wording: Before: Weekly fire drills. After: One clear quarterly rhythm. Story hashtags: #caseStudy #clientstory #beforeafter
**Day 8:** Use Stories to highlight a quote from your long-form post. Suggested wording: A single sharp sentence from the post on a branded background. Story hashtags: #quote #leadership #strategy
**Day 9:** Between heavier posts, Stories can carry light touchpoints. Suggested wording: Which would you choose right now? Big reset vs small consistent tweaks. Story hashtags: #thisorthat #poll #visibility
**Day 10:** Support a credibility post with proof of work. Suggested wording: This week in client work, with a short note over a blurred calendar or materials stack. Story hashtags: #clientwork #consulting #inprogress
**Day 11:** For content about mistakes, Stories can gather examples. Suggested wording: Tell me your strategy horror story (no names). Story hashtags: #storytime #businessmistakes #learnedthehardway
**Day 12:** When the feed post teaches a framework, Stories recap it visually. Suggested wording: Save this for your next quarterly review on the last frame of a 3–4 slide recap. Story hashtags: #framework #savethis #playbook
**Day 13:** On lighter days, Stories can keep you top of mind. Suggested wording: One win, one challenge this week — reply and tell me. Story hashtags: #checkin #weeklyreview #founders
**Day 14:** Tie Stories directly to your CTA. Suggested wording: If you want your next quarter to feel calmer, reply calm and I’ll send details. Story hashtags: #cta #booking #workwithme
**Day 15:** Use Stories to surface objections quietly. Suggested wording: Be honest: what's stopping you from revisiting your strategy? Story hashtags: #objections #truth #businesschat
**Day 16:** When the feed post shares your opinion, Stories invite theirs. Suggested wording: Agree or disagree with today’s post? Why? Story hashtags: #opinions #community #strategychat
**Day 17:** Support testimonial posts with context. Suggested wording: How we got there: 3 sessions, one clear rhythm. Story hashtags: #testimonial #clientjourney #results
**Day 18:** For nurture posts, Stories can give a small worksheet feel. Suggested wording: Screenshot and jot your answers on the last of a 3-question reflection. Story hashtags: #reflection #journaling #strategyquestions
**Day 19:** Use Stories to highlight your intake questions. Suggested wording: These are the questions we start with in every engagement. Story hashtags: #intake #questions #consulting
**Day 20:** On recap days, Stories collect feedback. Suggested wording: What do you want more of in April? Story hashtags: #feedback #planning #contentideas
**Day 21:** Give a visibility-focused micro-tip. Suggested wording: Most of our best-fit clients come from [channel] — here’s why. Story hashtags: #visibility #marketingtip #awareness
**Day 22:** Use Stories for a quick myth-busting follow-up. Suggested wording: Myth / What’s actually true over 2–3 frames. Story hashtags: #mythbusting #truth #strategy
**Day 23:** Align with a behind-the-scenes feed post. Suggested wording: What our internal strategy doc looks like (blurred, but real). Story hashtags: #bts #planning #operations
**Day 24:** When the feed shares a tip list, Stories can zoom into one tip. Suggested wording: If you only implement one thing from today’s post, make it this. Story hashtags: #tiptuesday #focus #execution
**Day 25:** Support rest or boundary posts with a human moment. Suggested wording: Strategy also needs space to think. Story hashtags: #rest #boundaries #founderlife
**Day 26:** Use Stories to show your tools. Suggested wording: These are the 3 tools I’d keep if I had to start over. Story hashtags: #tools #stack #workflow
**Day 27:** When you talk about pricing or value, Stories can soften it. Suggested wording: What you’re really buying is… Story hashtags: #pricing #value #worthit
**Day 28:** For community-focused posts, Stories highlight real names (with permission). Suggested wording: If you like today’s post, follow these people too. Story hashtags: #community #shoutout #network
**Day 29:** Use Stories to bridge into next month. Suggested wording: Planning next month’s content — what topic should I cover? Story hashtags: #comingsoon #planningahead #contentplan
**Day 30:** Close the loop with a simple thank-you + CTA. Suggested wording: If this month’s content helped, share your favourite post with someone who needs it. Story hashtags: #thankyou #roundup #sharethevalue
"""


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, "sample_30_days_story_ideas.pdf")
    logo_path = get_logo_path()
    if not logo_path:
        logo_path = os.path.join(root, "static", "images", "logo.png")
        if not os.path.isfile(logo_path):
            logo_path = None
    pdf_bytes = build_stories_pdf(SAMPLE_MD, logo_path=logo_path)
    if not pdf_bytes:
        print("Error: build_stories_pdf returned None. Check that SAMPLE_MD has a ## 30 Story Ideas section.")
        sys.exit(1)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Sample Story Ideas PDF written to: {out_path}")
    print("Open it to preview what customers receive with the Stories add-on.")


if __name__ == "__main__":
    main()
