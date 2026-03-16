# Test report — commit 49292b4 (post-deploy)

**Date:** 2025-02-12  
**Branch:** main  
**Deploy:** Pushed to `origin/main`; Railway (or connected host) will redeploy from this push.

---

## 1. Deploy summary

| Step | Status |
|------|--------|
| Commit (12 files) | ✅ Done |
| Push to origin/main | ✅ Done (`221abc2..49292b4`) |
| Redeploy | ✅ Triggered (if Railway/GitHub connected) |

**Included in commit:**
- Duplicate delivery guard + hashtag prompt (captions)
- Intake/reminder: login-first for subscribers, safe next redirect, intake login requirement
- Form buttons (account style), Account button mobile hover
- Currency-aware add-on prices (intake + downgrade/upgrade API)
- Email body audit extended; new test `test_captions_duplicate_and_hashtags.py`

---

## 2. Automated test results

| Test | Result | Notes |
|------|--------|------|
| `test_captions_duplicate_and_hashtags.py` | ✅ PASS | Duplicate guard + hashtag prompt checks |
| `check_email_bodies.py` | ✅ PASS | All 21 email flows have non-empty body |
| `check_email_branding.py` | ✅ PASS | All 9 templates use Lumo 22 branding |
| `test_reminder_toggle.py` | ✅ PASS | Reminder on/off toggle and cleanup |
| `test_deleted_account_blocklist.py` | ✅ PASS | Blocklist + resubscribe removal |
| `test_intake_business_name.py` | ✅ PASS | Business name in prompt and intake |
| **Flask app + routes** | ✅ PASS | `/`, `/captions`, `/login`, `/account`, `/api/captions-delivery-status` respond |
| `test_system.py` | ⚠️ 4/5 | OpenAI test fails (client `proxies` arg); config/Supabase/imports OK. Captions use Anthropic. |
| `test_intake_prefill_and_subscription.py` | ✅ PASS | Updated to patch `get_current_customer` for subscription intake so prefill and copy_from are still asserted. |

---

## 3. Scenarios and flows — what to test manually

Use **Stripe test mode** and **https://www.lumo22.com** (or your live URL after redeploy).

### 3.1 Landing and navigation
- [ ] Homepage loads; Captions in nav → captions page
- [ ] Log in / Sign up from nav
- [ ] Footer: Terms, Privacy (no Captions if removed)
- [ ] **Account** in nav (when logged in): hover on mobile → dark text

### 3.2 Captions product page
- [ ] Pricing and currency selector (GBP/USD/EUR if configured)
- [ ] Platform count 1–4; Story Ideas add-on when relevant
- [ ] One-off and subscription checkout links

### 3.3 Checkout (one-off)
- [ ] Terms modal; accept → Stripe test payment (4242…)
- [ ] Redirect to thank-you; order + intake emails received
- [ ] Intake email: “log in first” note and link; button → login then form

### 3.4 Checkout (subscription)
- [ ] Subscription checkout and test payment
- [ ] Thank-you + intake email (same login-first wording)

### 3.5 Intake form
- [ ] Open intake link from email (one-off): form loads (no login required for one-off)
- [ ] **Subscription order:** open intake link → redirect to **login**; after login → redirect back to intake form
- [ ] Submit with required fields empty → validation errors
- [ ] Fill and submit → success; delivery email with PDF
- [ ] **Buttons:** Next step, Edit, Send details look like account page (yellow hover)
- [ ] **Add another platform:** label shows correct currency (e.g. +$35 one-off / +$24/mo for USD)
- [ ] **Stories add-on:** label shows correct currency

### 3.6 Intake — upgrade/downgrade (subscription only)
- [ ] **Downgrade:** Reduce platforms or uncheck Stories → submit → “Accept new price — £X/month” (or $/€ for that order); accept → plan updates, form saves, success on same page
- [ ] **Upgrade (more platforms):** Select more platforms than paid → submit → “Confirm and accept new price” → opens **captions page** with correct `platforms` and `currency`; checkout again
- [ ] **Upgrade (Stories):** Check Stories without having it → same flow; link to captions with Stories

### 3.7 Login and post-login redirect
- [ ] Visit `/login?next=https://.../captions-intake?t=TOKEN` (subscription) → after login, redirect to that intake URL (not only account)

### 3.8 Reminder email (subscriber)
- [ ] Reminder email: CTA “Log in to update your form” → link is **login** with `next=` intake URL
- [ ] After login → land on intake form (pre-filled)

### 3.9 Account dashboard (logged in)
- [ ] Account page; Edit form → intake (pre-filled)
- [ ] Manage subscription: pause, resume, add/remove Stories, get pack sooner (modals and flow)

### 3.10 Delivery and duplicate guard
- [ ] One-off: submit intake once → **one** delivery email (no duplicate)
- [ ] If deliver-test or double-submit used, second run should skip (already delivered/generating)

### 3.11 Caption content
- [ ] Delivery PDF: when “include hashtags” was selected, **every** caption has a **Hashtags:** line (prompt strengthened)

### 3.12 Legal and redirects
- [ ] `/terms`, `/privacy` — dates 12 March 2026; burger menu visible on mobile
- [ ] `/digital-front-desk`, `/website-chat` → redirect to captions

---

## 4. Known / pre-existing

- **test_system.py** OpenAI check fails (client API); captions use Anthropic. Rest of system test passes.

---

## 5. Quick verification after redeploy

1. Open live URL (e.g. https://www.lumo22.com).
2. Hit `/captions` → product page loads.
3. Hit `/login` → login page loads.
4. Hit `/api/captions-delivery-status` → JSON with config check (no 500).
5. If you have a subscription intake link: open it in incognito → should redirect to login, then after login to the form.

---

*Report generated after commit and push; run manual checks above on live once deploy has finished.*
