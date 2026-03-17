# Testing division run — Lumo 22 Captions

**Run date:** Today  
**Agents used:** Reality Checker, Evidence Collector, Accessibility Auditor, API Tester  
**Automated tests:** Run and passed

---

## 1. Automated test results (just run)

| Suite | Result | What was checked |
|-------|--------|-------------------|
| **Upgrade flows** (`test_upgrade_flows.py`) | ✅ All passed | No "trial" in templates; trial only for upgrader without get-pack-now; invoice.paid copies intake from one-off; upgrade confirmation email exists; receipt skipped for trial. |
| **Subscription charges** (`test_subscription_charges.py`) | ✅ All passed | Display total × 100 = smallest unit; app formula and CAPTIONS_DISPLAY_PRICES match; 24 plan scenarios (currency × platforms × stories); trial/get-pack-now = one month charge. |
| **System** (`test_system.py`) | ✅ 3/3 passed | Imports, Supabase config, DB connection (caption_orders accessible). |

**Verdict:** Logic and pricing for upgrade flows and subscription amounts are covered by automated tests and passing.

---

## 2. Reality check — Production readiness

### 2.1 Current state (codebase + tests)

- **Stack:** Flask; captions, billing, auth, webhooks blueprints; no DFD/chat in use.
- **Config:** System test confirms Supabase. Stripe, SendGrid, BASE_URL, AI keys still not in `Config.validate()` — failures surface at runtime if missing.
- **Security:** `add_security_headers`; session HttpOnly, SameSite Lax. **Production:** set `SECRET_KEY` in env (no default in prod).
- **Upgrade flows (new):**
  - Upgrader **without** “Get your first pack now”: subscription created with trial; charge when first pack is ready; one email = “You’re set up” (no receipt).
  - Upgrader **with** “Get your first pack now”: charged at checkout; receipt + welcome email; pack delivered immediately.
  - First charge after trial = one month (same line_items); invoice.paid copies intake from one-off if missing.

### 2.2 Risks and gaps

- **No live/staging evidence:** Manual checklist still needs to be run on live (or staging) with screenshots.
- **Config:** Stripe, SendGrid, BASE_URL, AI keys not validated at startup.
- **Cron:** Reminder cron (`/api/captions-send-reminders`) needs `CRON_SECRET` and correct schedule on host.

### 2.3 Quality snapshot

- **Automated:** **B+** — Upgrade flows and charge amounts covered and passing.
- **Production readiness:** **Needs work** until manual test plan is run and critical env (including `SECRET_KEY`) is set.

---

## 3. Evidence plan (Evidence Collector)

Use **MANUAL_TEST_CHECKLIST.md** for the main flows. Add these steps for the **upgrade** flows.

### 3.1 Upgrade from one-off — charge on delivery (no “Get your first pack now”)

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| U1 | From upgrade reminder email (or link with `copy_from=TOKEN`), go to subscription checkout (logged in). | Checkout shows “You won’t be charged today” and charge date (e.g. “on 15 March 2026”). | Screenshot of checkout copy. |
| U2 | Complete checkout (no “Get your first pack now”). | Redirect to thank-you; **no** “We’ve received your payment” email. | Inbox: only “You’re set up — 30 Days Captions subscription” (with charge date). |
| U3 | Wait until trial end (or use Stripe test clock). | One charge = one month; pack generated and emailed. | Stripe invoice + delivery email. |

### 3.2 Upgrade from one-off — Get your first pack now

| Step | Action | Expected | Evidence |
|------|--------|----------|----------|
| U4 | Same checkout with **Get your first pack now** checked. | Copy says “You’ll be charged today”; price = one month (e.g. £79). | Screenshot. |
| U5 | Complete checkout. | Receipt email + “You’re subscribed” welcome; pack email shortly after. | Inbox: receipt + welcome + delivery. |

### 3.3 Summary

- **Total manual steps:** MANUAL_TEST_CHECKLIST.md (sections 1–10) + U1–U5 above.
- **Evidence to capture:** Screenshots of upgrade checkout (with/without “Get your first pack now”), thank-you, and relevant emails (set up vs receipt + welcome).

---

## 4. Accessibility (from previous audit)

- **Strengths:** `role="dialog"`, `aria-labelledby`, `aria-modal="true"` on modals; labels on key forms; nav and toggles have `aria-label` / `aria-expanded`.
- **Gaps:** Modal focus trap and return focus; “Skip to main content” link; consistent `:focus-visible` on interactive elements.
- **Action:** Before release, add focus trap + return focus in modals and a skip link; then re-check.

---

## 5. API coverage (API Tester angle)

- **Captions:** Checkout (one-off + subscription), intake link, intake submit, delivery status, download, pause/resume, get-pack-sooner, hide-pack, reminder preference, upgrade reminder unsubscribe, send-reminders (cron).
- **Billing:** Portal, payment method, add-stories, reduce-subscription, change-subscription-plan.
- **Webhooks:** Stripe (checkout.session.completed, invoice.paid, subscription updated/deleted, referral), Typeform, Zapier, SendGrid inbound, generic.
- **Auth:** Signup, login, forgot/reset, verify-email, change-email-confirm.

**Tests:** Subscription and upgrade logic and amounts are covered by `test_subscription_charges.py` and `test_upgrade_flows.py`. No Playwright/HTTP API tests in repo yet; manual or future automated E2E would cover full request/response.

---

## 6. Next steps

1. **Run manual checklist** on staging or live (Stripe test mode): MANUAL_TEST_CHECKLIST.md + upgrade steps U1–U5; record PASS/FAIL and save screenshots.
2. **Production env:** Set `SECRET_KEY`, Stripe, SendGrid, `BASE_URL`, AI keys; optionally extend `Config.validate()` for critical vars.
3. **Accessibility:** Implement modal focus trap + return focus and skip link; re-run accessibility pass.
4. **Optional:** Playwright (or similar) for screenshot capture and basic E2E; then re-run Reality Check with that evidence.

---

**Testing division:** Reality Checker + Evidence Collector + Accessibility Auditor + API Tester  
**Automated:** Upgrade flows + subscription charges + system — all passed.
