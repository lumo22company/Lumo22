# Lumo 22 Brand Style Guide

> **Lighting the way to better business**

---

## 1. Brand Overview

**Lumo 22** builds practical tools for small businesses and independents — designed to handle communication, content, and enquiries without noise.

**Products:**
- **Digital Front Desk** — Your virtual receptionist, 24/7. Replies instantly, qualifies leads, books appointments.
- **30 Days of Social Captions** — Done-for-you social content. Copy, edit, post.

**Positioning:**
- No dashboards to babysit. No robotic tone.
- Human-led, AI-assisted. Tools that scale your work.
- Built for busy people — founders and small teams.
- Clarity. Experience. Outcomes.

---

## 2. Logo & Wordmark

### Primary Wordmark
- **Form:** `Lumo 22` (always with a space; no "LUMO22")
- **Style:** Uppercase optional for nav/footers; preserve "22" as numeric

### Logo Usage
- On dark backgrounds: White (#ffffff) or off-white (#F5F5F2)
- On light backgrounds: Black (#000000)
- Hover states: Gold (#fff200)
- Minimum size: Readable at ~0.7rem with letter-spacing

### Do Not
- Stretch, rotate, or add effects to the wordmark
- Use alternate spellings (LUMO, Lumo22, Lumo-22)
- Pair with competing logos or clutter

---

## 3. Colour Palette

### Primary Colours

| Role | Hex | Usage |
|------|-----|-------|
| **Black** | `#000000` | Dark sections, hero, primary backgrounds |
| **Dark Surface** | `#000000` | Hero canvas, dark blocks |
| **Light Section** | `#e5e5e5` | Alternating content panels (Dayos-style) |
| **Accent Gold** | `#fff200` | Hover states, CTAs, labels, trust highlights |

### Text Colours

| Role | Hex | Usage |
|------|-----|-------|
| **Text on Dark** | `#F5F5F2` | Primary copy on black |
| **Text on Light** | `#000000` | Primary copy on light |
| **Muted** | `#9a9a96` | Secondary copy, footers |
| **Subtle** | `#6b6b68` | Tertiary, hints |

### Supporting Colours (Product Pages)

| Role | Hex | Usage |
|------|-----|-------|
| **Light Section BG** | `#f6f6f4` | Alternate product sections |
| **Ivory** | `#e8e6e2` | Soft surfaces |
| **Warm White** | `#ffffff` | Cards, nav CTA |

---

## 4. Typography

### Display / Headlines
- **Font:** Bebas Neue
- **Usage:** Hero wordmark, split panel titles, large headlines
- **Weight:** Default (single weight)
- **Letter-spacing:** Wide (`0.12em` hero, `0.1em` titles)
- **Fallback:** `sans-serif`

### Body
- **Font:** Century Gothic, CenturyGothic, Apple Gothic
- **Fallback:** `sans-serif`
- **Usage:** Body copy, nav links, descriptions, CTAs
- **Line-height:** 1.7
- **Letter-spacing:** `0.2em` for labels, nav, uppercase elements

### Condensed / Split Titles
- **Font:** PT Sans Narrow (optional, for editorial split layouts)
- **Weight:** 400, 700

### Hierarchy
- **Hero wordmark:** `clamp(4rem, 24vw, 16rem)` — Bebas Neue
- **Section titles:** Bebas Neue, scaled by context
- **Body:** Century Gothic, 1rem base

---

## 5. Spacing & Layout

### Spacing Scale (CSS Variables)
| Token | Value | Use |
|-------|-------|-----|
| `--space-xs` | 0.5rem | Tight gaps |
| `--space-sm` | 1rem | Inline spacing |
| `--space-md` | 1.5rem | Section padding |
| `--space-lg` | 2rem | Between elements |
| `--space-xl` | 3rem | Section spacing |
| `--space-2xl` | 4rem | Major breaks |
| `--space-3xl` | 6rem | Hero/section gaps |

### Section Spacing
- `--section-spacing`: 150px
- `--panel-margin`: 80px
- `--max-width`: 1100px
- `--max-width-narrow`: 580px

### Border Radius
| Token | Value | Use |
|-------|-------|-----|
| `--radius-btn` | 10px | Buttons, nav CTA |
| `--radius-card` | 20px | Cards, feature blocks |
| `--radius-section` | 40px | Large panel curves |
| `--radius-section-top` | 56px | Curved panel top edge |

---

## 6. Buttons & CTAs

### Primary CTA (Nav, Hero)
- **Background:** White (#ffffff)
- **Text:** Black (#000000)
- **Border-radius:** 10px
- **Letter-spacing:** 0.2em
- **Text-transform:** Uppercase
- **Hover:** Background → Gold (#fff200), `translateY(-3px)`
- **Transition:** 0.3s ease-in-out

### Secondary (Outlined / Muted)
- **Border:** 1px solid `--lum-border` or gold
- **Text:** White or `--lum-text-muted`
- **Hover:** Gold accent or lifted state

### Inline Links
- **Default:** White or `--lum-text-muted`
- **Hover:** Gold (#fff200)

---

## 7. Visual Language

### Editorial / Dayos-Inspired
- Alternating dark/light full-width sections
- Large rounded panels with curved top edges
- Split panels: 50/50, yellow grow-from-centre on hover (#fff200)
- Minimal borders; `rgba(255,255,255,0.06)` where needed
- Generous whitespace, clear hierarchy

### Motion
- **Easing:** `cubic-bezier(0.22, 1, 0.36, 1)`
- **Duration:** ~0.2s fast, ~0.35s normal
- Hero wordmark: fade-in ~1.2s
- Respect `prefers-reduced-motion: reduce`

---

## 8. Tone of Voice

### Principles
- **Clear** — Say what we do, no jargon
- **Confident** — Confident but not arrogant
- **Human** — Warm, approachable, never robotic
- **Practical** — Outcomes over features
- **Honest** — No hype, no lock-in pressure

### Voice Examples
- ✅ "Never miss a lead. Reply instantly."
- ✅ "No dashboards to babysit. No robotic tone."
- ✅ "Setup in minutes. Cancel anytime."
- ✅ "Human-led, AI-assisted."
- ❌ "Revolutionary AI-powered solution"
- ❌ "Best-in-class platform"

### Contact
- **Email:** hello@lumo22.com
- **Phrasing:** "Drop us a line →", "Questions or want to chat?"

---

## 9. Imagery & Iconography

- Prefer minimal, editorial imagery
- Avoid stock-photo clichés
- Use icons sparingly; favour typography and copy
- Canvas/volumetric mist in hero: subtle, black/neutral palette

---

## 10. File References

| Asset | Path |
|-------|------|
| Landing CSS | `static/css/landing.css` |
| Product CSS | `static/css/product.css` |
| Main style | `static/css/style.css` |

---

*Last updated: February 2025*
