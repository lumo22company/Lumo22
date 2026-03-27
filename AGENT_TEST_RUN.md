# Lumo 22 — Agent test run (Reality Checker + Evidence Collector + Accessibility Auditor)

**Date:** 2026-02-12  
**Scope:** Full site after redeploy (0645ee3); captions, upgrade flow, intake, account.  
**Agents:** Reality Checker (production readiness), Evidence Collector (test plan with evidence), Accessibility Auditor (WCAG).

---

## 1. Reality Checker — Production readiness

### 1.1 Stack and config (verified from codebase)

| Item | Status | Notes |
|------|--------|--------|
| **App** | OK | Flask; blueprints: `api_bp`, `webhook_bp`, `captions_bp`, `auth_bp`, `billing_bp`. No DFD/chat in use. |
| **Config.validate()** | Partial | Requires only `SUPABASE_URL`, `SUPABASE_KEY`. Captions need: `STRIPE_SECRET_KEY`, Stripe price IDs, `SENDGRID_API_KEY`, `BASE_URL`, `FROM_EMAIL`; generation needs `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. Not in `validate()` — missing = runtime errors. |
| **SECRET_KEY** | Risk | Defaults to `dev-secret-key-change-in-production`. **Must be set in production.** |
| **Security headers** | OK | `add_security_headers`: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS when HTTPS. |
| **Session** | OK | HttpOnly, SameSite Lax, 1h lifetime. |
| **Cron** | Depends | Reminder cron uses `CRON_SECRET`; host (e.g. Railway) must call `/api/captions-send-reminders` with correct secret. |

### 1.2 User journeys (from code)

| Journey | Implemented | Evidence to capture |
|---------|-------------|----------------------|
| Homepage → Captions → One-off checkout → Stripe → Thank-you → Intake email | Yes | Thank-you page, intake email, intake form load |
| Homepage → Captions → Subscription checkout (redirect to login if not logged in) → Stripe → Thank-you → Intake | Yes | Login redirect with `next`, then checkout, thank-you, intake email |
| Intake submit (one-off) → pack email | Yes | Delivery email / pack confirmation |
| Intake submit (subscription) → first pack | Yes | Same |
| Account: History, Edit form, Manage subscription (pause, add/remove Story Ideas, get pack sooner, manage billing) | Yes | Screenshots of sections and modals |
| One-off upgrade reminder (cron) → email → checkout with `copy_from` | Yes | Cron + email + checkout prefill |
| **Upgrade flow:** Account/upgrade → “Get my first subscription pack today” → “Edit form” → intake (no “Upgrade to subscription” CTA; stories reflect checkbox) → submit → back to /account/upgrade → checkout | Yes | Intake without CTA; `upgrade_stories` in URL; return to upgrade page |

### 1.3 Risks and gaps

- **No automated screenshot evidence** — All evidence is code-based. Run manual checklist on live/staging and capture screenshots for critical paths.
- **Config** — Stripe, SendGrid, BASE_URL, AI keys not validated in `validate()`; ensure production env is set.
- **SECRET_KEY** — Must be overridden in production.

### 1.4 Verdict

- **Production readiness:** **NEEDS WORK** — Implementation complete for current scope; live test run and production env (especially `SECRET_KEY`) required before certification.
- **Quality (code):** **B-** — Flows and upgrade/intake behaviour implemented; evidence and hardening pending.

---

## 2. Evidence Collector — Test plan with expected results

Execute on **https://www.lumo22.com** (or staging). Record PASS/FAIL and, where useful, a screenshot or one-line evidence.

### 2.1 Landing and navigation

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 1.1 | Load homepage | 200; logo and main message visible | e.g. screenshot-landing.png |
| 1.2 | Click **Captions** in nav | Navigate to `/captions` | URL + pricing visible |
| 1.3 | Click **Log in** | Navigate to `/login` | Login form |
| 1.4 | Click **Sign up** | Navigate to `/signup` | Signup form |
| 1.5 | Footer: Terms, Privacy, Captions | Each link works | 200 on each |

### 2.2 Captions product page

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 2.1 | Load `/captions` | Pricing (one-off and/or subscription) visible | Screenshot |
| 2.2 | Change currency (if present) | Prices update | Values shown |
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
| 5.4 | **Upgrade flow:** From upgrade page, “Get my first subscription pack today” → **Edit form** | Intake loads with `return_url=/account/upgrade`; **no** “Want a new pack every month?” / “Upgrade to subscription” CTA | No CTA block on page |
| 5.5 | **Upgrade flow:** On upgrade page uncheck Story Ideas, then open **Edit form** again | Intake shows Story Ideas in “add” mode (not “included”); “Align each Story…” unchecked | UI state |
| 5.6 | **Upgrade flow:** Submit intake | Redirect to `/account/upgrade` | URL and upgrade section visible |

### 2.6 Account (logged out)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 6.1 | Visit `/account` | Redirect to login | 302 → `/login` |
| 6.2 | Visit `/account/pause` | Redirect to login | 302 → `/login` |

### 2.7 Login and signup

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
| 8.3 | Edit form | Intake (pre-filled) for subscription orders only | Form + prefill |
| 8.4 | Referral: Copy link | Copies to clipboard (if enabled) | Paste elsewhere |

### 2.9 Manage subscription (/account/pause)

*(Requires active test subscription.)*

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 9.1 | Manage billing | Stripe Customer Portal | Portal opens |
| 9.2 | Pause for 1 month | Modal with resume date → confirm; row shows “Paused” + Resume | Modal + row state |
| 9.3 | Resume subscription | Row returns to active | Row state |
| 9.4 | Add Story Ideas (if not included) | Modal → confirm → row updates | Row state |
| 9.5 | Remove Story Ideas | Terms modal → accept → row updates | Row state |
| 9.6 | Get your pack sooner | First modal; “Use current details” → confirm modal; Cancel closes without charge | Modal + no charge |
| 9.7 | Get pack sooner → Update form → submit → yellow panel → Confirm and get my pack | Success; pack email later | Inbox |

### 2.10 Upgrade from one-off (subscription)

*(Need one-off order; use upgrade section or reminder email.)*

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 10.1 | **Charge on delivery:** Open subscription checkout; do **not** check “Get my first subscription pack today” | Copy says “You won’t be charged today” and shows charge date | Copy on page |
| 10.2 | Complete checkout (charge on delivery) | Thank-you; **only** “You’re set up — 30 Days Captions subscription” email (no “payment received” receipt) | Inbox |
| 10.3 | **Get your first pack now:** Open subscription checkout; check “Get my first subscription pack today” | Copy says “You’ll be charged today” | Copy on page |
| 10.4 | Complete checkout (get pack now) | Receipt email + “You’re subscribed” welcome; pack email arrives shortly after | Inbox |

### 2.11 Legal and legacy

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| 11.1 | `/terms` | Terms; “Last updated” visible | Page content |
| 11.2 | `/privacy` | Privacy; “Last updated” visible | Page content |
| 11.3 | `/digital-front-desk` | Redirect to captions | 302 → captions |
| 11.4 | `/website-chat` | Redirect to captions | 302 → captions |
| 11.5 | Nav/footer | No DFD or chat links | Visual check |

### 2.12 Summary

- **Total steps:** 45+ (expand sub-steps as needed).
- **Evidence:** Screenshots for thank-you, intake (normal and upgrade flow), account dashboard, key modals (terms, pause, get pack sooner).
- **Certification:** Mark each step PASS/FAIL; production certification only after critical paths (checkout, intake, account, upgrade flow, emails) all PASS and evidence is stored.

---

## 3. Accessibility Auditor — WCAG-focused review

### 3.1 Methodology

- **Automated:** Not run (no axe-core/Lighthouse in this run).
- **Manual (code):** Templates reviewed for semantics, ARIA, labels, and keyboard/focus.

### 3.2 What’s working well

- **Terms modal:** `role="dialog"`, `aria-labelledby="terms-modal-title"`, close button `aria-label="Close"`. Overlay `aria-hidden` toggled.
- **Intake form:** Most inputs have `<label for="...">`; groups use `role="group"` and `aria-label` (Primary audience, Voice tone, Platforms). Hashtag help has `aria-label="Hashtag guidelines"` and `tabindex="0"`.
- **Intake Edit preferences modal:** `role="dialog"`, `aria-labelledby`, `aria-modal="true"`, `aria-controls`/`aria-haspopup` on trigger.
- **Account dashboard:** Sidebar toggle `aria-expanded`, `aria-label="Toggle account menu"`. Modals use `role="dialog"`, `aria-labelledby`, `aria-modal="true"`. Toggles have `aria-label` (e.g. marketing). Payment method select has `aria-label="Choose card for this subscription"`.
- **Login/signup/reset:** Email and password fields have associated labels (`for=`).
- **Footer:** Logo link `aria-label="Lumo 22 home"`.

### 3.3 Issues and recommendations

| # | Issue | WCAG / impact | Severity | Recommended fix |
|---|--------|----------------|----------|------------------|
| 1 | Modal focus trap | 2.1.2 Keyboard | Serious | On open: move focus to first focusable element; trap Tab inside dialog; on close: return focus to trigger. Escape to close where applicable. |
| 2 | Skip link | 2.4.1 Bypass Blocks | Moderate | Add “Skip to main content” at top of body targeting `#main-content`; show on focus. |
| 3 | Focus visibility | 2.4.7 Focus Visible | Minor | Ensure `:focus-visible` (or `:focus`) is clearly visible on all interactive elements. |
| 4 | Some controls | 4.1.2 Name, Role, Value | Moderate | Verify every form control has a visible label or correct `aria-label`. |

### 3.4 Verdict

- **WCAG conformance:** **PARTIALLY CONFORMS** — Structure and many ARIA/label patterns in place; focus management in modals and skip link are main gaps.
- **Remediation priority:** Before release: focus trap and return focus in modals; add skip link. Short-term: confirm all form controls have labels; visible focus styles site-wide.

---

## 4. Automated test results (this run)

- **test_upgrade_flows.py:** 6 passed  
- **test_subscription_charges.py:** 5 passed  
- **test_extra_platform_stripe.py:** 1 passed  
- **test_system.py:** 3 passed (imports, config, Supabase)  

**Total:** 17 tests passed.

---

## 5. Recommended next steps

1. **Run the Evidence Collector plan** (Section 2) on **live or staging**: execute each step, record PASS/FAIL, capture screenshots for critical journeys (checkout, intake, upgrade flow, account).
2. **Production config:** Set `SECRET_KEY`, Stripe vars, SendGrid, `BASE_URL`, AI keys; consider extending `Config.validate()` for critical vars.
3. **Accessibility:** Implement modal focus trap and return focus; add “Skip to main content” link; audit focus visibility.
4. **Re-assess:** After manual run and fixes, update this document with final Production Readiness and WCAG conformance.

---

**Agents:** Reality Checker + Evidence Collector + Accessibility Auditor  
**Deploy:** 0645ee3 (intake CTA hidden in upgrade flow)  
**Evidence location:** Manual test results + screenshots (to be stored)
