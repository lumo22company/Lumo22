# Lumo 22 Remediation Plan — Security, Privacy & Platform Fixes

**Created:** 2026-02-12  
**Status:** ✅ Implemented 2026-02-12

**Constraint:** This plan excludes all visual/UI changes. Only backend, config, and non-visual fixes.

---

## How to Use This Plan

1. **Review** each item below.
2. **Approve** — Tell me when you're ready: "Go ahead with the remediation plan."
3. **Implementation** — I will make changes one item at a time.
4. **Verification** — After each change, I will run a quick check to ensure nothing is broken before proceeding.

---

## Priority 1: Critical (Fix First)

### 1.1 Fix undefined `pack_start_for_pdf` in pack download (NameError → 500)

| Source | Security H3 / E2E #1 |
|--------|----------------------|
| **Location** | `api/captions_routes.py` lines 1245, 1264 |
| **Issue** | `pack_start_for_pdf` is never defined; Stories PDF download raises `NameError`. |
| **Fix** | Use `date_str` (already defined above) instead of `pack_start_for_pdf` in both `build_stories_pdf()` and `build_caption_pdf()` calls. |
| **Visual** | None |

---

### 1.2 Add auth to billing subscription endpoints (IDOR)

| Source | Security H1 / E2E #2 |
|--------|----------------------|
| **Location** | `api/billing_routes.py` — `reduce_subscription()`, `change_subscription_plan()` |
| **Issue** | Anyone with an order token can change another user's subscription. |
| **Fix** | Add `get_current_customer()` at start; return 401 if not logged in; verify `order["customer_email"]` matches `customer["email"]` before applying changes. |
| **Visual** | None |

---

## Priority 2: High (Security & Privacy)

### 2.1 Restrict intake link by email (token disclosure)

| Source | Security H2 |
|--------|-------------|
| **Location** | `api/captions_routes.py` — `captions_intake_link_by_email()` |
| **Issue** | Unauthenticated; returns intake URL (with token) for any email. |
| **Fix** | Require login and verify session email matches requested email before returning the intake URL. If not logged in, return 401 and rely on thank-you page's session_id flow or email fallback with rate limiting. |
| **Visual** | None (thank-you page flow may require user to be logged in for email fallback — confirm flow) |

---

### 2.2 Data export endpoint (GDPR portability)

| Source | Privacy #1 |
|--------|------------|
| **Location** | New route: `GET /api/auth/export-data` (authenticated) |
| **Issue** | Privacy policy promises data portability; no implementation. |
| **Fix** | Add authenticated endpoint returning JSON of account data (email, orders summary, intake fields). No new UI — user could call via browser devtools or we add a link later (link = visual, optional). |
| **Visual** | None |

---

### 2.3 500 handler return HTML when request prefers HTML

| Source | E2E #4 |
|--------|--------|
| **Location** | `app.py` — `internal_error`, `catch_all_exception` |
| **Issue** | 500 always returns JSON; users see raw JSON instead of friendly page. |
| **Fix** | When `Accept` includes `text/html`, render 500 template; otherwise return JSON. |
| **Visual** | None (improves error page experience) |

---

## Priority 3: Medium (Config & Hardening)

### 3.1 Session cookie Secure flag in production

| Source | Security M1 / Privacy #12 |
|--------|---------------------------|
| **Location** | `config.py` |
| **Issue** | `SESSION_COOKIE_SECURE = False`; cookie sent over HTTP. |
| **Fix** | Set `SESSION_COOKIE_SECURE = True` when `Config.is_production()` or when HTTPS is detected (e.g. `X-Forwarded-Proto: https`). |
| **Visual** | None |

---

### 3.2 Restrict CORS origins

| Source | Security M2 / Privacy #11 |
|--------|---------------------------|
| **Location** | `app.py` |
| **Issue** | `CORS(app)` allows any origin. |
| **Fix** | Restrict to known origins: `CORS(app, origins=[Config.BASE_URL, "https://www.lumo22.com", "https://lumo22.com"].filter(), supports_credentials=True)` or equivalent. |
| **Visual** | None |

---

### 3.3 Restrict or disable debug endpoint

| Source | Security M4 |
|--------|-------------|
| **Location** | `app.py` — `GET /debug-deploy` |
| **Issue** | Exposes deploy details without auth. |
| **Fix** | Require `?secret=DEBUG_SECRET` (when set) or disable in production. |
| **Visual** | None |

---

### 3.4 WebAuthn credentials deleted on account deletion

| Source | Privacy #3 |
|--------|------------|
| **Location** | `api/auth_routes.py` — `delete_account()` |
| **Issue** | Passkey rows left in Supabase when account is deleted. |
| **Fix** | Call `WebAuthnCredentialService().delete_all_for_customer(customer_id)` before deleting customer. |
| **Visual** | None |

---

### 3.5 Stripe customer deletion on account deletion

| Source | Privacy #4 |
|--------|------------|
| **Location** | `api/auth_routes.py` — `delete_account()` |
| **Issue** | Stripe customer records retained after local deletion. |
| **Fix** | Fetch Stripe customer IDs from caption_orders; call `stripe.Customer.delete()`. Handle 404; log non-critical errors. |
| **Visual** | None |

---

### 3.6 Marketing opt-in default to `false` (GDPR)

| Source | Privacy #6 |
|--------|------------|
| **Location** | `database_customers_marketing.sql` (migration), `services/customer_auth_service.py` |
| **Issue** | `marketing_opt_in` defaults to `true`; GDPR requires explicit consent. |
| **Fix** | Change DB default to `false`; ensure signup/create does not set `marketing_opt_in=true` unless explicitly provided. **No new checkbox** — that would be visual. Just change default. |
| **Visual** | None (existing users keep current value; new users default to false) |

---

### 3.7 Idempotency for intake link by email (prevent duplicate emails)

| Source | E2E #9 |
|--------|--------|
| **Location** | `api/captions_routes.py` — `captions_intake_link_by_email()` |
| **Issue** | Repeated requests can resend intake email multiple times. |
| **Fix** | Add cooldown (e.g. don't resend if last sent &lt; 5 minutes) or track `last_intake_email_sent_at` per order. |
| **Visual** | None |

---

### 3.8 Diagnostic endpoints: require auth or secret

| Source | Security M6 |
|--------|-------------|
| **Location** | `api/auth_routes.py` — `/api/auth/forgot-password/status`; `api/captions_routes.py` — `/api/captions-delivery-status` |
| **Issue** | Expose config state without auth. |
| **Fix** | Require `?secret=CRON_SECRET` or similar, or restrict to internal IP. Alternatively, require login for captions-delivery-status if used by admins. |
| **Visual** | None |

---

## Priority 4: Low (Nice to Have)

### 4.1 Reduce PII in logs

| Source | Security L3 / Privacy #9 |
|--------|--------------------------|
| **Location** | Multiple: `api/webhooks.py`, `api/auth_routes.py`, `api/captions_routes.py`, `services/notifications.py` |
| **Issue** | Full emails in `print()` and logs. |
| **Fix** | Redact: e.g. `user***@***.com` or hash. Replace `print()` with structured logging where appropriate. |
| **Visual** | None |

---

### 4.2 Ensure SHOW_500_DETAIL never enabled in production

| Source | Security M5 |
|--------|-------------|
| **Location** | `api/captions_routes.py`, any 500 handler |
| **Issue** | If `SHOW_500_DETAIL=1` in production, stack traces leak. |
| **Fix** | In code: if `Config.is_production()`, never include detail in response regardless of env. Document in .env.example. |
| **Visual** | None |

---

### 4.3 Generic/Zapier/Typeform webhooks: return 2xx or remove

| Source | Security L1 / E2E #3 |
|--------|----------------------|
| **Location** | `api/webhooks.py` |
| **Issue** | Return 410; integrations treat as failure. |
| **Fix** | Return 200 with no-op body if webhooks are deprecated; or add auth if re-enabled. |
| **Visual** | None |

---

### 4.4 SendGrid inbound webhook verification

| Source | Security L2 |
|--------|-------------|
| **Location** | `api/webhooks.py` — `/webhooks/sendgrid-inbound` |
| **Issue** | No signature verification. |
| **Fix** | Verify SendGrid signature when inbound parsing is enabled. |
| **Visual** | None |

---

### 4.5 Update privacy policy: OpenAI, blocklist retention

| Source | Privacy #5, #10 |
|--------|-----------------|
| **Location** | `templates/_privacy_content.html` |
| **Issue** | OpenAI not listed as subprocessor; blocklist retention not disclosed. |
| **Fix** | Add "OpenAI and/or Anthropic"; add sentence about blocklist for post-deletion. |
| **Visual** | Text-only change in policy page |

---

## Excluded (Would Change Visuals)

These were flagged but **excluded** from this plan because they require UI changes:

- Add marketing opt-in checkbox on signup
- Add Terms/Privacy links on signup
- Add cookie consent banner
- Add "Download my data" link in account (endpoint only is in plan; link is optional later)

---

## Verification Checklist (After Each Change)

- [ ] Run app locally: `flask run` or `python app.py`
- [ ] Hit affected route and confirm no 500
- [ ] Run existing tests if any: `pytest` or equivalent
- [ ] Quick smoke test: login, captions flow, account page

---

## Summary Table

| #   | Priority | Item                                      | File(s)                    |
|-----|----------|-------------------------------------------|----------------------------|
| 1.1 | Critical | Fix pack_start_for_pdf                    | captions_routes.py         |
| 1.2 | Critical | Auth on billing subscription endpoints    | billing_routes.py          |
| 2.1 | High     | Restrict intake link by email             | captions_routes.py         |
| 2.2 | High     | Data export endpoint                      | auth_routes.py (new)       |
| 2.3 | High     | 500 handler HTML for browsers             | app.py                     |
| 3.1 | Medium   | Session cookie Secure                     | config.py                  |
| 3.2 | Medium   | CORS restrict origins                     | app.py                     |
| 3.3 | Medium   | Restrict debug endpoint                   | app.py                     |
| 3.4 | Medium   | Delete WebAuthn on account deletion       | auth_routes.py             |
| 3.5 | Medium   | Delete Stripe customer on deletion        | auth_routes.py             |
| 3.6 | Medium   | Marketing default false                   | DB migration, service      |
| 3.7 | Medium   | Intake email idempotency                  | captions_routes.py         |
| 3.8 | Medium   | Diagnostic endpoints auth                 | auth_routes, captions      |
| 4.1 | Low      | PII redaction in logs                     | Multiple                   |
| 4.2 | Low      | SHOW_500_DETAIL guard in production       | captions_routes, app       |
| 4.3 | Low      | Webhooks 2xx or auth                      | webhooks.py                |
| 4.4 | Low      | SendGrid inbound verification             | webhooks.py                |
| 4.5 | Low      | Privacy policy text updates               | _privacy_content.html      |

---

---

## Post-Implementation: Manual Steps Required

1. **Run DB migration** for marketing default:
   - Execute `database_customers_marketing_default_false.sql` in Supabase SQL Editor
   - This changes the default for new rows; code already sets `marketing_opt_in=False` on signup

2. **Optional env vars** (for production):
   - `DEBUG_DEPLOY_SECRET` — When set, `/debug-deploy` requires `?secret=DEBUG_DEPLOY_SECRET`
