# Account page — analysis and improvement suggestions

## What it does today

- **Route:** `/account` (login required). Loads customer, Front Desk/Chat setups, and caption orders; renders `customer_dashboard.html`.
- **Sections:**
  1. **Hero** — "Your account", email, quick links (Captions · Front Desk · Pricing), Log out.
  2. **Billing alerts** — Shown when `?billing=no_sub` or `?billing=error` (after Stripe portal redirect).
  3. **Digital Front Desk & Chat** — Cards per setup: badge (DFD vs Chat), business name, enquiry email, forwarding (DFD), Pause/Resume auto-reply links (DFD), or embed code (Chat).
  4. **30 Days Captions** — "Manage subscription" if any order has `stripe_customer_id`; cards per order with status, Complete form / Edit form, Download captions (if delivered), Contact us.
  5. **Settings** — Marketing emails toggle (PATCH `/api/auth/preferences`).

- **Data:** `setups` from `FrontDeskSetupService.get_by_customer_email`, `caption_orders` from `CaptionOrderService.get_by_customer_email`. Both keyed by logged-in customer email.

---

## What works well

- Single place for DFD, Chat, and Captions.
- Logout and marketing toggle work.
- Caption download is protected (login + order must match customer email).
- Billing portal link and redirect handling in place.
- Responsive layout and existing product.css account styles (dark/light sections, cards, badges).

---

## Suggested improvements

### 1. **UX / clarity**

| Issue | Suggestion |
|-------|------------|
| Caption order title is only "Order YYYY-MM-DD" | Add a short label, e.g. "30 Days Captions · Order 12 Feb 2025" or show platform count / subscription vs one-off. |
| No feedback when marketing toggle is clicked | Show a short "Saved" or "Updated" message (or toast) after a successful PATCH. |
| Pause/Resume auto-reply are raw API links | Use buttons or styled links and, if possible, indicate current state (Paused / Active) so the user doesn’t have to guess. |
| Empty states are minimal | Add one line of copy, e.g. "When you buy Digital Front Desk or Captions, your setups and orders will appear here." |

### 2. **Security / robustness**

| Issue | Suggestion |
|-------|------------|
| Front Desk pause/resume use `done_token` in URL | Tokens in URLs can leak (referrer, logs). Prefer POST from the account page with token in body or session, and ensure the API validates that the setup belongs to the logged-in customer (e.g. by email). |
| `customer` in template is a dict; template uses `customer.email` | Prefer `customer.get('email')` in Jinja (e.g. `{{ customer.get('email', '') }}`) so a missing key doesn’t break the page. |

### 3. **Subscription / billing**

| Issue | Suggestion |
|-------|------------|
| "Manage subscription" shown if *any* caption order has `stripe_customer_id` | Logic is reasonable; consider clarifying in UI: "Manage Captions subscription" so it’s clear which product it affects. |
| No link to billing when user has no subscription | If you want to support "upgrade" or "view payment method" for one-off buyers, add a small link or note for caption orders without a subscription (e.g. "One-off purchase — no subscription to manage"). |

### 4. **Visual / brand**

| Issue | Suggestion |
|-------|------------|
| Fonts: Encode Sans Condensed + Bebas + Inter | Align with BRAND_STYLE_GUIDE: Bebas Neue (display), Century Gothic (body). Swap Encode Sans Condensed for Century Gothic where body/UI text is used so account matches the rest of the site. |
| Nav CTA says "Account" when already on account | Consider "Account" that stays, or a small indicator (e.g. "You’re logged in as …") so it’s clear they’re in their account. |

### 5. **Technical / accessibility**

| Issue | Suggestion |
|-------|------------|
| Logout form is submitted via JS (fetch + redirect) | Keep one path: either form POST or JS. If you keep JS, add a loading state and handle errors (e.g. show "Log out failed. Try again."). |
| Marketing toggle has `onclick` and `onkeydown` | Good. Add `aria-pressed` or `aria-checked` so the state is announced (e.g. `aria-pressed="true"` when on). |
| Embed code is in `<pre>` | Add a "Copy" button so users can copy the embed snippet in one click. |

### 6. **Optional enhancements**

- **Password change** — Link or section to change password (e.g. "Change password" → existing reset flow or a dedicated change-password page).
- **Order sorting** — Show caption orders newest first (if not already).
- **Status wording** — Map internal statuses to user-friendly labels (e.g. `awaiting_intake` → "Complete your form", `generating` → "Creating your captions", `delivered` → "Delivered", `failed` → "Issue — contact us").

---

## Priority summary

| Priority | Action |
|----------|--------|
| High | Safe template access for email: `{{ customer.get('email', '') }}`. |
| High | Harden pause/resume: validate setup ownership by customer email; consider POST with token in body instead of GET with token in URL. |
| Medium | Marketing toggle: success feedback + `aria-pressed` / `aria-checked`. |
| Medium | Copy button for Chat embed code. |
| Medium | Clearer caption order titles and "Manage Captions subscription" label. |
| Low | Align account page fonts with BRAND_STYLE_GUIDE (Century Gothic for body). |
| Low | Password change entry point and friendlier status labels. |

Implementing the high-priority items first will improve security and reliability; the rest will improve clarity and polish.
