# Lumo 22 — Security & privacy review

**Date:** 2026-02-12  
**Method:** In-repo audit (Security Engineer + API + compliance-style pass). **Not** a penetration test or legal review.

---

## Executive summary — top risks

| # | Severity | Topic |
|---|----------|--------|
| 1 | **High** | **`GET /api/captions-webhook-test`** is unauthenticated: creates a **real** `caption_orders` row and sends a **real** intake email to any `?email=` (default `test@example.com`). Abusable for spam, DB noise, and SendGrid cost. |
| 2 | **High** (conditional) | **`GET /api/captions-deliver-test`** — if **`CAPTIONS_DELIVER_TEST_SECRET` is unset** in production, anyone who obtains a valid order **token** or **Stripe `session_id`** can trigger **AI generation + delivery** (cost + email flood). |
| 3 | **Medium** | **`SECRET_KEY`** defaults to `dev-secret-key-change-in-production` if env missing — session forgery risk. Mitigated if `Config.validate()` runs at startup in production (it enforces a changed key when `is_production()`). |
| 4 | **Medium** | **`CORS(app)`** with default Flask-CORS settings often allows **any origin** for cross-origin requests — widen attack surface for cookie-using APIs if any exist. Tighten to known front-end origins if APIs are browser-called. |
| 5 | **Medium** | **`SESSION_COOKIE_SECURE = False`** — session cookie may be sent without `Secure` flag (comment notes HTTPS-terminating proxy). Prefer `True` when the app sees HTTPS via `X-Forwarded-Proto` and Flask `ProxyFix`, or set at reverse proxy. |
| 6 | **Low–Med** | **Logging**: many `print(...)` paths include **customer email** or partial IDs — PII in host logs (Railway, etc.). Prefer structured logs with redaction. |
| 7 | **Low** | **`/webhooks/generic`** and **Zapier** routes accept JSON and create leads **without shared secret** — spam / fake leads (business risk more than data breach). |
| 8 | **Privacy (doc)** | Policy lists **Anthropic** as AI processor; **`OPENAI_MODEL`** path also sends intake to **OpenAI** when `AI_PROVIDER=openai`. Policy should name both or say “our AI provider(s)”. |

**Strong positives:** Stripe webhook uses **`stripe.Webhook.construct_event`** (signature verification). Cron route **`/api/captions-send-reminders`** checks **`CRON_SECRET`**. Security headers (X-Frame-Options, nosniff, Referrer-Policy, HSTS when HTTPS). Intake/download tokens use **`secrets.token_urlsafe`**. Production **`Config.validate()`** enforces key secrets. Caption orders use **Supabase anon key** server-side with expectation of **RLS** (confirm policies in Supabase for `caption_orders` / customers).

---

## Threat model (short)

```
[Browser] --HTTPS--> [Flask] --TLS--> [Supabase / Stripe / SendGrid / AI APIs]
                         ^
                         |-- POST /webhooks/stripe (signed)
                         |-- POST /webhooks/* (mixed)
                         |-- GET/POST /api/* (sessions, tokens, cron secret)
```

**Trust boundaries:** Public internet → Flask; Flask must verify Stripe signatures, cron secret, and customer session/token for account & download routes. Supabase: server holds anon key; **service role** used only in selected services (`CustomerAuthService`, `ReferralRewardService`, etc.) — must never reach the client.

---

## Findings (detail)

### Authentication & session

| Item | Notes |
|------|--------|
| Session | HttpOnly, SameSite=Lax, 1h lifetime (`config.py`). |
| SECRET_KEY | Default dev value; production validation requires override. |
| Secure cookie | Disabled for proxy compatibility — review for your deployment. |
| One-time login tokens | In-memory store `_login_tokens` in `app.py`, short TTL — OK for mitigation; clears on restart. |

### Stripe

| Item | Notes |
|------|--------|
| Webhook POST | Payload verified with **`STRIPE_WEBHOOK_SECRET`** — **good**. |
| GET `/webhooks/stripe` | Harmless status JSON. |

### Cron & test endpoints

| Route | Risk |
|-------|------|
| `/api/captions-send-reminders` | **401** without correct `CRON_SECRET` — **good**. |
| `/api/captions-webhook-test` | **No auth** — **fix or disable in production** (see recommendations). |
| `/api/captions-deliver-test` | Optional secret; **if unset, effectively public** for anyone with token/session_id — **set secret in all production environments**. |

### Other webhooks

| Route | Risk |
|-------|------|
| `/webhooks/sendgrid-inbound` | Returns `200` with empty body — no signature check visible; low impact if no parsing; could still be used for noise/DoS. If you later parse inbound mail, add verification. |
| `/webhooks/generic`, Zapier | Unauthenticated ingestion into lead flow. |

### Data access (IDOR / tokens)

| Item | Notes |
|------|--------|
| `captions-download` | Requires logged-in customer; order must match **email** — good pattern. |
| `captions-intake?t=` | Knowledge of **unguessable token** grants form access — OK if token length/entropy kept (`token_urlsafe(16)`). |
| Supabase RLS | **Verify** in dashboard: customers cannot `select` other users’ `caption_orders` via anon key abuse (e.g. leaked key in browser — you don’t expose it in front-end for orders, good). |

### Headers & transport

| Item | Status |
|------|--------|
| X-Frame-Options, X-Content-Type-Options, Referrer-Policy | Set in `add_security_headers`. |
| HSTS | Set when `request.is_secure` or `X-Forwarded-Proto=https`. |
| CSP | **Not** set — optional hardening for XSS defense-in-depth. |

### AI & intake privacy

| Item | Notes |
|------|--------|
| Intake dict | Sent to OpenAI or Anthropic per `AI_PROVIDER` — aligns with “caption generation” in policy if both named. |
| Logs | Avoid logging full intake JSON in production. |

### Privacy policy vs practice (assistive)

| Policy says | Code / ops |
|-------------|------------|
| Stripe, SendGrid, Supabase, Anthropic | Matches; add **OpenAI** when used. |
| Technical / IP data | Confirm retention and whether you log IPs at proxy only. |
| Account deletion | Ensure Supabase deletes align with stated retention. |

---

## Code changes applied (2026-02-12)

- **`/api/captions-webhook-test`:** returns **404** when `Config.is_production()` so unauthenticated order+email abuse is blocked in production (still available locally / non-prod for debugging).
- **`/api/captions-deliver-test`:** in production, returns **403** until **`CAPTIONS_DELIVER_TEST_SECRET`** is set; when set, `?secret=` is still required as before.

## Recommended actions (prioritised)

1. ~~**Remove or protect `/api/captions-webhook-test` in production**~~ — **Done** (404 in production).

2. ~~**Set `CAPTIONS_DELIVER_TEST_SECRET` in production**~~ — **Enforced** (403 until set; then use `?secret=`). **Action for you:** add `CAPTIONS_DELIVER_TEST_SECRET` to Railway/hosting vars if you still use deliver-test in production.

3. **Tighten CORS** to specific origins if any browser client calls your API with credentials.

4. **Re-evaluate `SESSION_COOKIE_SECURE`** with your hosting (Railway + custom domain HTTPS often works with `ProxyFix` + `True`).

5. **Reduce PII in prints** — use logging levels and redact emails in production.

6. **Update `_privacy_content.html`** — subprocessors: “OpenAI and/or Anthropic depending on configuration” (or list both with links).

7. **Non-AI (still do):** `pip-audit` / Dependabot, optional OWASP ZAP on staging, periodic secrets scan.

---

## Sign-off

This document is an **internal technical review**. It does **not** certify GDPR compliance, SOC 2, or absence of vulnerabilities. Re-run after major feature or infra changes.

**Related:** `PRIVACY_SECURITY_AGENT_RUN.md`, `WEBSITE_TEST_WITH_AGENTS.md`, `AGENT_TEST_RUN.md`.
