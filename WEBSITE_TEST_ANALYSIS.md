# Lumo 22 — Website test analysis

**Product:** Lumo 22 (30 Days Captions) — Flask app  
**Scope:** Full site: landing → product → checkout → intake → account  
**Sources:** Reality Checker (production readiness), Evidence Collector (test plan), Accessibility Auditor (WCAG)  
**Date:** 2025-02-12

---

## Executive summary

- **Production readiness:** **NEEDS WORK** — Core flows are implemented and config is validated; live testing and evidence (screenshots, Stripe/SendGrid in production) are still required before certification.
- **Test plan:** The manual checklist (`MANUAL_TEST_CHECKLIST.md`) is turned into a concrete test plan with expected results and evidence to capture below.
- **Accessibility:** **PARTIALLY CONFORMS** — Good use of `role="dialog"`, `aria-label`, and `label for=` on key pages; gaps remain (focus trap in modals, some form labels, contrast/skip links).

**Recommended next steps:** Run the test plan on staging/live, capture screenshots for critical journeys, fix accessibility gaps (focus management, skip link), then re-run Reality Check and accessibility pass.

---

## 1. Reality Check — Production readiness

### 1.1 What was verified (codebase)

- **Stack:** Flask app; blueprints: `api_bp`, `webhook_bp`, `captions_bp`, `auth_bp`, `billing_bp`. No DFD/chat routes in use; legacy API routes return 410/redirects.
- **Config:** `Config.validate()` requires only `SUPABASE_URL` and `SUPABASE_KEY`. Captions flows also depend on `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SENDGRID_API_KEY`, `BASE_URL`, and (for generation) `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. No validation for these in `validate()` — if missing, failures will occur at runtime.
- **Security:** `add_security_headers` (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS when HTTPS). Session: HttpOnly, SameSite Lax, 1h lifetime. `SECRET_KEY` defaults to `dev-secret-key-change-in-production` — **must be overridden in production**.
- **Flows:** Landing → Captions product → Checkout (one-off/subscription) → Thank-you → Intake (token-based) → Account (login required for subscription intake). Subscription checkout requires login; one-off upgrade reminder and prefilled form flows are implemented.

### 1.2 User journeys (from code)

| Journey | Status | Evidence needed |
|--------|--------|------------------|
| Homepage → Captions → One-off checkout → Stripe → Thank-you → Intake email | Implemented | Screenshot thank-you + intake email + intake form load |
| Homepage → Captions → Subscription checkout (redirect to login if not logged in) → Stripe → Thank-you → Intake email | Implemented | Same + login redirect with `next` |
| Intake form submit (one-off) → pack email | Implemented | Delivery email + PDF or pack confirmation |
| Intake form submit (subscription) → first pack | Implemented | Same |
| Account: pause / resume / get pack sooner / edit form / manage billing | Implemented | Screenshots of account sections and modals |
| One-off upgrade reminder (cron) → email → checkout with `copy_from` | Implemented | Cron hit + email + checkout prefill |

### 1.3 Risks and gaps

- **No automated screenshot evidence:** No Playwright/automated capture was run; all “evidence” is code-based. Reality Checker standard is to run `qa-playwright-capture.sh` (or equivalent) and review screenshots — **not done**.
- **Config validation incomplete:** Stripe, SendGrid, BASE_URL, AI keys not in `validate()`; wrong/missing env in production will surface as runtime errors.
- **SECRET_KEY:** If `SECRET_KEY` is not set in production, session security is weak.
- **Cron:** Reminder cron (`/api/captions-send-reminders`) depends on `CRON_SECRET`; ensure Railway (or host) cron is configured and secret set.

### 1.4 Realistic quality certification

- **Overall:** **B-** (implementation complete; evidence and hardening pending).  
- **Production readiness:** **NEEDS WORK** — Run full manual test plan on live/staging, capture evidence, set production env (especially `SECRET_KEY`), then re-assess.

---

## 2. Test plan & evidence (Evidence Collector)

Use this to run tests and record results. For each step, note **PASS/FAIL** and, where useful, a screenshot or one-line evidence.

### 2.1 Landing & navigation

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 1.1 | Load homepage | 200; logo and main message visible | e.g. `screenshot-landing.png` |
| 1.2 | Click **Captions** in nav | Navigate to `/captions` | URL + pricing visible |
| 1.3 | Click **Log in** | Navigate to `/login` | Login form |
| 1.4 | Click **Sign up** | Navigate to `/signup` | Signup form |
| 1.5 | Footer: Terms, Privacy, Captions | Each link works | 200 on each |

### 2.2 Captions product page

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 2.1 | Load `/captions` | Pricing (one-off and/or subscription) visible | Screenshot |
| 2.2 | Change currency (if selector present) | Prices update | Values shown |
| 2.3 | Change platform count | UI updates | e.g. 1 vs 2 platforms |
| 2.4 | If IG+FB selected, check Story Ideas | Add-on appears if applicable | UI state |
| 2.5 | Click one-off checkout CTA | Terms modal or checkout page | Modal or URL |
| 2.6 | Click subscription checkout CTA | Login if not logged in; else checkout | Redirect or Stripe |

### 2.3 Checkout (one-off)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 3.1 | Reach checkout page | Correct price and summary | Screenshot |
| 3.2 | Click “Next step — read & accept terms” | Terms modal opens | Modal visible |
| 3.3 | Scroll to bottom of terms | “I have read and agree” enables | Button enabled |
| 3.4 | Accept terms | Redirect to Stripe | Stripe Checkout URL |
| 3.5 | Pay with 4242 4242 4242 4242 | Success; redirect to thank-you | Thank-you page |
| 3.6 | Check email | Confirmation + intake link email | Inbox (subject/link) |

### 2.4 Checkout (subscription)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 4.1 | Reach subscription checkout | Monthly price and summary | Screenshot |
| 4.2 | Terms modal | Same behaviour as one-off | Modal + agree |
| 4.3 | Complete Stripe subscription | Thank-you; confirmation + intake email | Inbox |

### 2.5 Intake form

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 5.1 | Open intake link (from email or token URL) | Form loads (login required if subscription) | Form visible |
| 5.2 | Submit with required fields empty | Error at top; fields highlighted | Error message |
| 5.3 | Fill required fields and submit | Success message; pack email (one-off) or first pack (subscription) | Success + email |

### 2.6 Account (logged out)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 6.1 | Visit `/account` | Redirect to login | 302 → `/login` |
| 6.2 | Visit `/account/pause` | Redirect to login | 302 → `/login` |

### 2.7 Login & signup

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 7.1 | Sign up | Activation email sent | Inbox |
| 7.2 | Click activation link | Can log in | Login success |
| 7.3 | Log in with email/password | Land on account/dashboard | Account page |
| 7.4 | Log out | Account link no longer in nav | Nav state |
| 7.5 | Forgot password → reset | Reset email → new password works | Inbox + login |

### 2.8 Account dashboard (logged in)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 8.1 | Account page | 30 Days Captions section visible | Screenshot |
| 8.2 | Past packs: Download | PDF opens/downloads | File or preview |
| 8.3 | Edit form | Intake (pre-filled) | Form + prefill |
| 8.4 | Referral: Copy link | Copies to clipboard (if enabled) | Paste elsewhere |

### 2.9 Manage subscription (/account/pause)

(Requires active test subscription.)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 9.1 | Manage billing | Stripe Customer Portal | Portal opens |
| 9.2 | Pause for 1 month | Modal with resume date → confirm; row shows “Paused” + Resume | Modal + row state |
| 9.3 | Resume subscription | Row returns to active | Row state |
| 9.4 | Add Story Ideas (if not included) | Modal → confirm → row updates | Row state |
| 9.5 | Remove Story Ideas | Terms modal → accept → row updates | Row state |
| 9.6 | Get your pack sooner | First modal; “Use current details” → confirm modal; Cancel closes without charge | Modal + no charge |
| 9.7 | Get pack sooner → Update form → submit → yellow panel → Confirm and get my pack | Success; pack email later | Inbox |

### 2.10 Legal & legacy

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 10.1 | `/terms` | Terms; “Last updated” visible | Page content |
| 10.2 | `/privacy` | Privacy; “Last updated” visible | Page content |
| 10.3 | `/digital-front-desk` | Redirect to captions | 302 → captions |
| 10.4 | `/website-chat` | Redirect to captions | 302 → captions |
| 10.5 | Nav/footer | No DFD or chat links | Visual check |

### 2.11 Summary

- **Total steps:** 40+ (expand sub-steps as needed).  
- **Evidence to capture:** Screenshots for thank-you, intake form, account dashboard, key modals (terms, pause, get pack sooner). Optional: `test-results.json` if you add Playwright later.  
- **Honest outcome:** Mark each step PASS/FAIL; count failures. **Production certification** only after critical paths (checkout, intake, account, emails) all PASS and evidence is stored.

---

## 3. Accessibility audit (Accessibility Auditor)

### 3.1 Methodology

- **Automated:** Not run (no axe-core/Lighthouse run in this analysis).  
- **Manual (code):** Templates reviewed for semantics, ARIA, labels, and keyboard/focus patterns.

### 3.2 What’s working well

- **Landing:** `<main id="main-content">`, hero scroll button has `aria-label="Scroll to explore"`, decorative hero image has `alt=""`, `aria-hidden` used appropriately.
- **Nav:** Mobile toggle has `aria-label="Toggle navigation"` and `aria-expanded="false"`.
- **Terms modal:** `role="dialog"`, `aria-labelledby="terms-modal-title"`, close button `aria-label="Close"`. Overlay `aria-hidden` toggled on open/close.
- **Intake form:** Most inputs have `<label for="...">`; groups use `role="group"` and `aria-label` (e.g. Primary audience, Voice tone, Platforms). Hashtag help has `aria-label="Hashtag guidelines"` and `tabindex="0"`.
- **Edit preferences modal (intake):** `role="dialog"`, `aria-labelledby`, `aria-modal="true"`.
- **Account dashboard:** Sidebar toggle `aria-expanded` and `aria-label="Toggle account menu"`. Modals (pause, get pack sooner, add/remove stories, delete pack, delete account) use `role="dialog"`, `aria-labelledby`, `aria-modal="true"`. Delete account input has `aria-describedby` for hint. Toggles have `aria-label` (e.g. marketing, form reminders).
- **Login/signup/forgot/reset:** Email and password fields have associated labels (`for=`).
- **Captions product:** Section `aria-label="Example and format"`; platform error has `role="alert"`; sticky CTA has `aria-label="Quick action"`.

### 3.3 Issues found

| # | Issue | WCAG / impact | Severity | Location | Recommended fix |
|---|--------|----------------|----------|----------|------------------|
| 1 | Modal focus trap | 2.1.2 Keyboard (operable) | Serious | All dialogs (terms, pause, get pack sooner, intake edit preferences, account modals) | On open: move focus to first focusable element; trap Tab inside dialog; on close: return focus to trigger. Add Escape to close where applicable. |
| 2 | Skip link | 2.4.1 Bypass Blocks | Moderate | Site-wide | Add “Skip to main content” link at top of body targeting `#main-content`; show on focus. |
| 3 | Some inputs without visible labels | 4.1.2 Name, Role, Value | Moderate | Account: new email input, payment method select (has `aria-label`; verify visible label where needed) | Ensure every form control has a visible label or `aria-label` and that it’s correct. |
| 4 | Focus visibility | 2.4.7 Focus Visible | Minor | Global | Ensure `:focus-visible` (or `:focus`) is clearly visible on all interactive elements (buttons, links, inputs, toggles). |
| 5 | Decorative hero logo | 1.1.1 Non-text Content | Pass | Landing hero | `alt=""` is correct for decorative image. |

### 3.4 Summary

- **WCAG conformance:** **PARTIALLY CONFORMS** — Structure and many ARIA/label patterns are in place; focus management in modals and skip link are the main gaps.  
- **Assistive technology:** **PARTIAL** — Keyboard users may have trouble with modals (no trap/return focus); screen reader users will get most structure and labels.  
- **Remediation priority:**  
  - **Before release:** Implement focus trap and focus return in all modals; add skip link.  
  - **Short-term:** Confirm all form controls have visible or programmatic labels; enforce visible focus styles site-wide.

---

## 4. Recommended next steps

1. **Run the test plan** (Section 2) on **staging or live** (Stripe test mode): execute each step, record PASS/FAIL, and capture screenshots for thank-you, intake, account, and key modals.  
2. **Set production config:** Ensure `SECRET_KEY`, `STRIPE_*`, `SENDGRID_*`, `BASE_URL`, and AI keys are set; consider extending `Config.validate()` for critical vars.  
3. **Accessibility:** Implement modal focus trap and return focus; add “Skip to main content” link; audit focus visibility.  
4. **Optional:** Add Playwright (or similar) to capture screenshots and, if desired, basic interaction tests; re-run Reality Check with that evidence.  
5. **Re-assess:** After fixes and a full manual run, update this document with a final Production Readiness and WCAG conformance line.

---

**Integration Agent:** Reality Checker + Evidence Collector + Accessibility Auditor  
**Evidence location:** Manual test results + screenshots (to be stored)  
**Re-assessment:** After test run and accessibility fixes
