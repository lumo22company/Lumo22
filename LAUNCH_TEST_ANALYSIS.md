# Lumo 22 — Pre-launch test analysis

**Date:** 3 March 2026  
**Scope:** Automated tests, code paths, config, and launch readiness.

---

## 1. Automated test results

| Test suite | Result | Notes |
|------------|--------|------|
| **Password validation** | ✅ Pass | `validate_password()` enforces 10+ chars + 1 number. |
| **test_intake_prefill_and_subscription.py** | ✅ Pass | Prefill from `copy_from`, subscribe_url includes `copy_from` and `stories=1`, no subscribe_url for subscription orders. |
| **test_intake_add_platform_visibility.py** | ✅ Pass | “Add another platform” visibility and upgrade_required for Stories. |
| **test_referral_discount.py** | ✅ Pass | Referral coupon applied when ref valid (mocked). |
| **test_system.py** | ✅ Pass | Imports, config, lead model, OpenAI, Supabase all OK. |
| **test_intake_business_name.py** | ⚠️ 1 fail | `test_multi_platform_prompt_includes_rotation_instruction` expects "Assign each day" and "balanced rotation" in the **user** prompt. The caption generator uses different wording ("For EACH day (1–30), write one caption for EACH of these platforms..."). **Product behaviour is correct**; the test expectation is outdated. Optional: update the test to match current prompt text or remove the assertion. |

**Summary:** Core flows (auth, intake, subscription, referral, prefill) pass. One failing test is a wording mismatch in the prompt test, not a functional bug.

---

## 2. Critical paths reviewed

### Auth & account
- **Signup** (`/signup`, `POST /api/auth/signup`): Password validated (10 chars + 1 number) in service and routes; templates show correct hints and `minlength="10"`.
- **Login** (`/login`, `POST /api/auth/login`): Email + password; session set; no password rules on login (correct).
- **Create account** (intake / front-desk): `POST /api/auth/create-account` uses same `validate_password()`; templates updated.
- **Reset password** (`/reset-password`, `POST /api/auth/reset-password`): Token validated, `validate_password()` applied; templates and JS check length + number.
- **Forgot password**: Request reset → email with link → reset page with token. Depends on SendGrid and `BASE_URL` for link.

### Captions purchase flow
- **Product page** (`/captions`): Currency selector, platforms, Story Ideas checkbox, one-off vs subscription CTAs.
- **Checkout**: One-off and subscription create Stripe Checkout with correct metadata (platforms, stories, currency, `copy_from` when applicable).
- **Thank-you** (`/captions-thank-you`): Uses `session_id`; backend fetches session and shows intake link when order exists.
- **Intake** (`/captions-intake?t=TOKEN`): Loads order by token; prefill from `copy_from` when same customer; submit can trigger immediate delivery or scheduled (upgrade-from-one-off).
- **Delivery**: `_run_generation_and_deliver`; email with PDF(s); `set_delivered`; subscription renewal via `invoice.paid` webhook.

### Account dashboard
- **Sections:** Information, History, Edit form, Manage subscription, Refer a friend.
- **Manage subscription:** Payment method dropdown (custom arrow), pause/resume (pause_collection modify), Add/Remove Story Ideas (add-stories-to-subscription, reduce-subscription).
- **Resume subscription:** Uses `stripe.Subscription.modify(sub_id, pause_collection="")` (correct for pause_collection; not `Subscription.resume()`).

### Billing & Stripe
- **Webhook** (`/webhooks/stripe`): `checkout.session.completed` and `invoice.paid` (subscription_cycle) for captions; referral on `invoice.created` where applicable.
- **Add Stories:** Adds Stories price to existing subscription; proration; order `include_stories` updated.
- **Remove Stories:** Reduce-subscription removes Stories line item; order updated; new price from next invoice.

### Browsing & static
- **Landing** (`/`), **Terms** (`/terms`), **Captions** (`/captions`), **404**: Routes registered; terms “Last updated: 3 March 2026”.
- **Plans** (`/plans`): Redirects to `/captions#pricing`.

---

## 3. Configuration checklist (Railway / env)

Confirm these for production:

| Variable | Purpose |
|----------|---------|
| `BASE_URL` | https://www.lumo22.com (or your live domain). Used in emails, Stripe success URLs, webhook base. |
| `STRIPE_SECRET_KEY` | Live key when going live. |
| `STRIPE_WEBHOOK_SECRET` | Secret for `POST /webhooks/stripe` (e.g. `https://www.lumo22.com/webhooks/stripe`). |
| `SUPABASE_URL`, `SUPABASE_KEY` or `SUPABASE_SERVICE_ROLE_KEY` | Customers, caption_orders, password reset. |
| `SENDGRID_API_KEY`, `FROM_EMAIL` | Transactional email (intake, delivery, password reset). |
| `OPENAI_API_KEY` | Caption (and story) generation. |
| `CAPTIONS_PAYMENT_LINK` | Optional; Checkout Sessions used for captions flow. |
| `STRIPE_CAPTIONS_PRICE_ID` | One-off captions (GBP). |
| `STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID` | Subscription (GBP). |
| `STRIPE_CAPTIONS_STORIES_PRICE_ID`, `STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID` | Story Ideas add-on. |
| `STRIPE_CAPTIONS_EXTRA_PLATFORM_*` | If offering multi-platform. |
| `STRIPE_REFERRAL_COUPON_ID` | Optional; refer-a-friend discount. |
| `CRON_SECRET` | If using Railway cron for `/api/captions-send-reminders` (scheduled deliveries). |
| `SECRET_KEY` | Flask session; set a strong random value in production. |

Stripe Dashboard:
- Success URLs for Checkout point to `{BASE_URL}/captions-thank-you` (and any other success pages you use).
- Webhook endpoint: `https://www.lumo22.com/webhooks/stripe` (or your live URL); events: `checkout.session.completed`, `invoice.paid`, `invoice.created` (if using referral).

---

## 4. Optional / known gaps

- **test_intake_business_name.py:** One assertion fails on exact prompt wording ("Assign each day" / "balanced rotation"). Behaviour is correct; update or relax the test if you want the suite fully green.
- **apscheduler:** Reminder scheduler logs “No module named 'apscheduler'” in some test runs; `apscheduler` is in `requirements.txt`. Ensure it’s installed in the environment where reminders run (e.g. Railway).
- **Config.validate():** Only checks `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`. It does not enforce Stripe or SendGrid for captions; app will 503 or fail at runtime if those are missing when used.

---

## 5. Manual testing (high level)

Use **WEBSITE_TEST_CHECKLIST.html** for step-by-step checks. Priority:

1. **Domain & SSL:** Visit https://www.lumo22.com (or live URL); confirm SSL and redirects.
2. **Captions:** Select platforms + optional Stories → Get my 30 days or Subscribe → complete with test card 4242… → thank-you → intake link → submit form.
3. **Account:** Signup (password 10+ chars + 1 number) → login → Account Information, Edit form, Manage subscription (payment method, pause, Add/Remove Story Ideas), Refer a friend, Log out.
4. **Password reset:** Forgot password → email → reset link → new password (10+ chars + 1 number) → login.
5. **Emails:** Intake and delivery emails received; from address and links correct.
6. **Subscription:** Add Stories from account; Remove Story Ideas; pause then resume (no “only resume if paused” error).

---

## 6. Summary

- **Automated tests:** Core behaviour passes; one non-functional test failure (prompt wording).
- **Critical paths:** Auth (signup, login, create-account, reset) and captions (product → checkout → thank-you → intake → delivery) are consistent with current design; account and billing (pause/resume, add/remove Stories) are wired correctly.
- **Launch readiness:** Code and flows look ready for launch provided env and Stripe (URLs, webhook, success URLs) are set correctly and you run through the manual checklist (especially one full captions purchase and one subscription + account actions).

If you want, the next step can be: (1) updating `test_intake_business_name.py` so the multi-platform prompt test matches current copy or is skipped, and (2) a short “go-live” checklist of env and Stripe settings to tick off on the day.
