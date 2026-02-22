# Lumo 22 — Website analysis & psychology-backed UX/conversion plan

## 1. Current state: what’s working

### Landing page
- **Clear value frame:** “Two simple tools that save time and mental space” sets expectation without clutter.
- **Low cognitive load:** Hero (brand) → Intro (what we do) → Split (choose product) → Trust → Footer. No long paragraphs.
- **Strong visual hierarchy:** Mist hero, light/dark alternation, split panels with clear CTAs.
- **Obvious next step:** “Explore” in nav and split panels (Digital Front Desk / 30 Days Captions) give a single, clear path.
- **Trust block:** “Why Lumo 22” (No lock-in, Human-led, Built for busy people) addresses risk and identity in a few lines.

### Digital Front Desk product page
- **Benefit-first structure:** Hero promise → Features (4 cards) → How it works (3 steps) → Testimonials → Pricing → FAQ → Footer.
- **Single primary CTA:** “View Plans” in hero scrolls to pricing; “Activate now” on cards and “Customize Your Front Desk” after How it works.
- **Reduced uncertainty:** FAQ (collapsible), compare table, add-on note answer “what do I get?” and “what if I want chat?”.
- **Social proof:** Three named testimonials (Ella, James, Priya) with roles; “Recommended” on Growth.
- **Consistent styling:** Off-white/black sections, rounded cards, left-aligned headings, nav-CTA style on pricing buttons.
- **Scannable layout:** Feature grid, step numbers + icons, pricing grid + table.

### Activate / checkout path
- **Short path:** Product page → Activate (plan choice + T&Cs) → Stripe → Success. Few steps.
- **Plan clarity:** Starter / Growth / Pro with price and short description; optional Chat add-on with toggle.
- **Trust:** T&Cs checkbox, “no setup calls” messaging.

---

## 2. Gaps and what’s left to do

### Broken or inconsistent
- **“Try the concierge” and `/#front-desk`:** The concierge/chat section was removed from the homepage. Nav CTA and “Front Desk” links still point to `/#front-desk`, which no longer exists. Users land at top of homepage with no clear “concierge” experience. **Fix:** Either restore a minimal concierge/chat block on the homepage, or change the nav CTA (e.g. “View plans” or “Get started”) and links to `/plans` or `/digital-front-desk` so the promise matches the page.
- **Plans page vs rest of site:** Plans uses different nav (e.g. “Get started” → `/signup`), different layout (style.css vs landing.css), and anchors like `/#how-it-works`, `/#products` that may not exist on the current landing. **Fix:** Align nav, styles, and anchor links with the live landing structure (e.g. `/#lumo-split` for “Explore” / product choice).

### Missing or weak for conversion
- **No urgency or scarcity:** No “limited capacity”, “setup in 24h”, or time-bound offer. Risk of “I’ll do it later” (procrastination).
- **No concrete outcome stats:** Testimonials are qualitative only. Numbers (“saved X hours”, “Y% faster reply”) would strengthen credibility (availability heuristic + social proof).
- **No risk reversal above the fold:** “Cancel anytime” appears in pricing copy but not in hero or first CTA. Refund/guarantee not prominent.
- **Single CTA flavour:** Almost everything is “Activate now” or “View plans”. No secondary path like “See a demo” or “Talk to us” for high-intent but not-ready-to-buy visitors.
- **Mobile:** Layout is responsive but key interactions (split panels, pricing cards, FAQ) should be checked on small screens for tap targets and readability.

### Content / SEO
- **Meta:** Landing title still “Social Captions & Digital Front Desk”; description mentions “30 days” and “digital front desk”. Fine for now; can be refined per primary product.
- **Captions product:** Has its own page; flow from landing split is clear. No major structural gap.

---

## 3. Structure assessment

| Area              | Assessment |
|-------------------|------------|
| **Information architecture** | Clear: Home → Product (Front Desk or Captions) → Activate/Plans → Checkout. No dead ends. |
| **Landing flow**  | Good: Identity → Benefit → Choice (split) → Trust. Could add one short “How it works” or “Why us” before trust. |
| **DFD page flow** | Strong: Problem implied in hero → Features → How it works → Proof → Price → Objection handling (FAQ). Matches “awareness → consideration → decision”. |
| **Navigation**    | Consistent links (Captions, Front Desk, Pricing). CTA and “Front Desk” hrefs need fixing (see above). |
| **Visual hierarchy** | Headings and sections are clearly separated; alternating backgrounds support scanning. |

**Verdict:** Structure is sound. Main fixes are broken links/CTAs and a few high-impact conversion additions (urgency, proof, risk reversal), not a full restructure.

---

## 4. Psychology-backed plan to improve UX and conversion

Principles used: **cognitive load**, **social proof**, **authority**, **scarcity/urgency**, **loss aversion**, **commitment**, **clarity**, **trust**, **friction reduction**.

### Priority 1 — Fix broken expectations (trust + clarity)
- **Update “Try the concierge” and `/#front-desk`:**  
  - Option A: Point nav CTA and “Front Desk” links to `/digital-front-desk` or `/plans` and change CTA label to “View plans” or “Get started” so the experience matches.  
  - Option B: Reintroduce a small concierge/chat block on the homepage and keep the CTA, but ensure the section id and copy are correct.
- **Align Plans page:** Same nav as rest of site (e.g. lumo-nav), remove or update anchors that don’t exist on the current landing.

*Why:* Broken promises (clicking “Try the concierge” and not getting it) reduce trust and increase drop-off. Clarity and consistency support System 2 (deliberate) decisions.

### Priority 2 — Reduce perceived risk (loss aversion + trust)
- **Surface “Cancel anytime” and “No setup calls”** in hero or first CTA area on the DFD page (e.g. one short line under “View Plans”).
- **Add a short guarantee** if you have one (e.g. “30-day guarantee” or “Pause or cancel anytime”) near pricing or above the fold.
- **Keep FAQ and compare table** as they are; they already answer objections and reduce uncertainty.

*Why:* Loss aversion is strong; small, clear risk-reversal lines lower the perceived cost of trying.

### Priority 3 — Strengthen social proof (authority + availability)
- **Add one or two outcome-focused stats** to the DFD page, e.g. “Reply in under 2 minutes” or “Businesses save X hours per week on enquiry handling.” Use real numbers if you have them; otherwise plausible, defensible estimates.
- **Optional:** Add “As used by X+ businesses” or “Trusted by [type]” near testimonials if accurate.
- **Keep testimonials as-is** (named, role, short quote). Consider adding a photo or logo later for authenticity.

*Why:* Specific numbers and “others like you” make benefits more concrete (availability heuristic) and increase perceived credibility.

### Priority 4 — Light urgency (scarcity/commitment)
- **Soft, honest urgency only:** e.g. “Setup in 24 hours” or “Limited onboarding slots this month” only if true. Avoid fake countdowns or fake scarcity.
- **Alternative:** Emphasise “Go live in 24 hours” or “No long implementation” to reduce “I’ll do it later” by making the first step feel quick.

*Why:* Real urgency can nudge commitment; fake urgency damages trust.

### Priority 5 — One clear secondary path (reduced friction for “not yet”)
- **Add a single secondary CTA** for visitors who aren’t ready to activate, e.g. “Questions? Email us” or “Book a short call” (if you offer it) in footer or below pricing. Keeps the main CTA “Activate now” / “View plans” as primary.

*Why:* Offering one alternative path can reduce bounce without diluting the main action.

### Priority 6 — Small UX polish
- **Sticky or visible CTA on scroll:** On DFD page, consider a slim “View plans” or “Activate” bar that appears after hero scroll (optional; test so it doesn’t feel pushy).
- **Pricing visibility:** Ensure the “Recommended” Growth card stands out (you already do this); ensure first visible CTA on mobile is above the fold.
- **Mobile tap targets:** Ensure “Activate now”, “View plans”, and FAQ summary are at least 44px and well spaced.

*Why:* Visibility of the next action and ease of tapping support conversion, especially on mobile.

### What to avoid
- **Too many CTAs** on one screen (paradox of choice).
- **Long paragraphs** in hero or first screen (keep cognitive load low).
- **Fake scarcity or fake testimonials** (backfire on trust).
- **New sections that duplicate** the product page (you already removed repetition; keep it that way).

---

## 5. Suggested order of work

1. **Fix nav and links:** “Try the concierge” / `/#front-desk` and Plans page anchors (Priority 1).
2. **Add one risk-reversal line** on DFD hero or just below “View Plans” (Priority 2).
3. **Add 1–2 outcome stats** on DFD if you have or can state numbers (Priority 3).
4. **Optional:** One soft urgency or “quick setup” line; one secondary CTA in footer (Priorities 4–5).
5. **Optional:** Sticky CTA and mobile tap-audit (Priority 6).

---

## 6. Summary

- **Working:** Clear structure, benefit-first DFD page, strong trust block on landing, simple activate flow, good use of social proof and FAQ.
- **To do:** Fix broken “Try the concierge” / `#front-desk` and Plans anchors; add risk-reversal line; add outcome stats; optional urgency, secondary CTA, and mobile polish.
- **Structure:** Solid; no need for a big restructure.
- **Psychology plan:** Fix broken promises first (trust), then risk reversal, then proof (stats), then light urgency and one secondary path, then small UX improvements—all in line with reducing cognitive load, increasing trust, and making the next step obvious and low-friction.
