# Marketing Site Implementation

## What Was Built

A premium, dark-mode marketing site with x.ai/dayos-inspired aesthetic. Launch-ready.

### Pages

1. **Homepage** (`/` → `templates/landing.html`)
   - Hero with dark mist animation, minimal headline, CTA
   - Offer: 30 Days of Social Media Captions (price: £97 — change in `.lumo-offer-price`)
   - Digital Front Desk: conversational intake (chat-style)
   - Trust section (no fake testimonials)
   - Footer

2. **Digital Front Desk product page** (`/digital-front-desk` → `templates/digital_front_desk.html`)
   - Full product description, how it works, pricing
   - Dark design system applied

### Files

| File | Purpose |
|------|---------|
| `static/css/landing.css` | Design system: colors, typography, sections |
| `static/js/mistDark.js` | Dark atmospheric hero mist |
| `static/js/front-desk.js` | Digital Front Desk conversational logic |
| `static/js/landing.js` | Scroll reveal, nav behavior |

## Assumptions

- **Price**: £97 for 30 Days Captions (placeholder in HTML)
- **AI integration**: Digital Front Desk uses scripted flow; for real AI, add `window.LUMO_AI_ENDPOINT` and POST `{ message, history }`
- **Email**: All CTAs use `mailto:hello@lumo22.com`
- **Dark mode only**: No light theme

## Changing the Price

In `templates/landing.html`, find:

```html
<div class="lumo-offer-price">£97 <span>one-time</span></div>
```

Edit the value and span text.

## AI Integration (Digital Front Desk)

To replace scripted responses with an AI backend:

1. Add an API endpoint (e.g. `/api/qualify`) that accepts `{ message: string, history: array }`
2. In `front-desk.js`, set `window.LUMO_AI_ENDPOINT = '/api/qualify'`
3. Replace the scripted flow with `fetch()` calls and dynamic rendering
4. See comments in `front-desk.js` for stubs

## Design Tokens

Defined in `landing.css` (`:root`):

- `--lum-black`, `--lum-surface`, `--lum-text`, `--lum-text-muted`
- `--lum-gold`, `--lum-gold-soft` (accent)
- `--font-display`, `--font-body`
- `--ease-out`, `--duration-normal`, etc.

## Run

```bash
./run.sh
# or
python3 app.py
```

Homepage: http://localhost:5001/  
Digital Front Desk: http://localhost:5001/digital-front-desk
