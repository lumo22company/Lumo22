# Redeploy & full website test report

**Date:** 2026-02-12  
**Deploy:** Pushed to `main` (0645ee3)  
**Scope:** Redeploy, automated tests, testing-division style review, manual test plan

---

## 1. Redeploy

- **Committed:** `app.py`, `templates/captions_intake.html`
- **Message:** Intake: hide Upgrade to subscription CTA when in upgrade flow (return_url=account/upgrade)
- **Pushed:** `main` → origin (0645ee3)
- **Host:** Will pick up from GitHub; allow 1–2 minutes for build.

---

## 2. Automated tests (all passed)

| Suite | Tests | Result |
|-------|--------|--------|
| **test_upgrade_flows.py** | 6 | All passed |
| **test_subscription_charges.py** | 5 | All passed |
| **test_extra_platform_stripe.py** | 1 | Passed |
| **test_system.py** (pytest) | 3 | All passed |
| **test_system.py** (script) | 3/3 | PASS: Imports, Config, Supabase |

**Total:** 17 pytest tests passed (24 deprecation/warnings, non-blocking).

**Coverage:** No trial wording in templates; billing_anchor for upgraders without get_pack_now; invoice.paid copies intake; upgrade confirmation email; receipt skipped for trial; “Get my first subscription pack today” + Edit form first UI; display/formula/addon/scenario pricing; Extra platform Stripe setup; system imports, config, Supabase.

---

## 3. Testing division–style review

### 3.1 Reality Check (production readiness)

- **Codebase:** Captions-only; upgrade flow (charge on delivery vs get pack now), intake with `upgrade_stories` and `is_upgrade_flow`, CTA hidden in upgrade flow. No DFD/chat in use.
- **Config:** Supabase validated in tests; Stripe/SendGrid/BASE_URL not in `validate()` — ensure production env is set.
- **Session:** `SECRET_KEY` must be set in production.
- **Verdict:** Implementation complete for current scope; run manual flows on live and confirm env (especially SECRET_KEY, Stripe, SendGrid).

### 3.2 Evidence (what to verify manually)

Use **MANUAL_TEST_CHECKLIST.md** on https://www.lumo22.com (or staging). Priority:

1. **Landing & nav** — Home, Captions, Log in, Sign up, footer.
2. **Captions page** — Pricing, currency, platforms, Story Ideas, checkout links.
3. **One-off checkout** — Terms modal, Stripe test card, thank-you, intake email.
4. **Subscription checkout** — Login redirect with `next`, then Stripe; thank-you and emails.
5. **Intake form** — From email (one-off): required validation, submit, success. **Upgrade flow:** From upgrade page → “Edit form” (Get my first subscription pack today) → intake has **no** “Want a new pack every month?” / “Upgrade to subscription” CTA; Story section reflects `upgrade_stories` (uncheck on upgrade page → intake shows add mode, align unchecked); submit → return to /account/upgrade.
6. **Account** — Login/signup, dashboard, History, Edit form (subscription only), Manage subscription (pause, add/remove Story Ideas, get pack sooner).
7. **Upgrade from one-off** — Charge on delivery: copy + no receipt email. Get pack now: copy + receipt + welcome + pack email.
8. **Legal** — /terms, /privacy; old routes redirect.

### 3.3 Accessibility (quick pass)

- Modals: `role="dialog"`, `aria-modal`, `aria-labelledby` in place.
- Forms: `label for=`, required indicators; focus and contrast to be confirmed on live.
- **Action:** Run Lighthouse (Accessibility) on key pages after deploy.

---

## 4. Manual test checklist (upgrade-flow intake)

Add to your run of **MANUAL_TEST_CHECKLIST.md**:

**10b. Upgrade flow — intake form (Get my first pack today → Edit form)**

- [ ] Upgrade page: select one-off, check “Get my first subscription pack today”. “Do you need to update your form?” and **Edit form** button appear.
- [ ] Click **Edit form**. Intake loads with `return_url=/account/upgrade` and `upgrade_stories=0` or `1` from checkbox.
- [ ] **No** “Want a new pack every month?” / “Upgrade to subscription — [business]” block on that intake page.
- [ ] Uncheck Story Ideas on upgrade page, then open Edit form again: intake shows Story Ideas in “add” mode (not “included”), align unchecked.
- [ ] Submit intake → redirect back to /account/upgrade. Complete checkout (e.g. get pack now) → expected emails and behaviour.

---

## 5. Summary

| Item | Status |
|------|--------|
| Redeploy | Pushed to `main` (0645ee3) |
| Automated tests | 17/17 passed |
| System (imports, config, DB) | 3/3 passed |
| Reality Check | Implementation complete; env and live evidence pending |
| Evidence plan | MANUAL_TEST_CHECKLIST.md + section 10b above |
| Accessibility | Partial; Lighthouse on live recommended |

**Next:** Run **MANUAL_TEST_CHECKLIST.md** (and 10b) on live/staging, capture screenshots for critical journeys, and confirm env (SECRET_KEY, Stripe, SendGrid) on the host.
