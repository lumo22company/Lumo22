# Privacy & security testing with Agency agents (Lumo 22)

Use this alongside **`WEBSITE_TEST_WITH_AGENTS.md`**. Install the rules you need from [agency-agents](https://github.com/msitarzewski/agency-agents) into `.cursor/rules/` (see that repo’s README for Cursor rule format).

**Disclaimer:** AI-assisted review is not a substitute for a professional penetration test, formal compliance audit, or legal advice on GDPR / UK GDPR / privacy policy text.

---

## 1. Agents to add (recommended order)

| Priority | Source in agency-agents | Role |
|----------|-------------------------|------|
| 1 | `engineering/engineering-security-engineer.md` | App security, OWASP-style review, secrets, auth |
| 2 | `testing/testing-api-tester.md` | APIs, webhooks, auth boundaries |
| 3 | `specialized/compliance-auditor.md` | Privacy/compliance *alignment* (policy vs practice) |
| 4 | `engineering/engineering-threat-detection-engineer.md` | Optional: logging, abuse, detection |

You already use **Reality Checker** for production readiness (includes some security items) — run it in parallel or first.

---

## 2. Copy-paste prompts (Cursor Chat)

### 2.1 Security Engineer — full pass

```
Use the Security Engineer agent (or act as an application security engineer using the same rigour).

Stack: Flask app (Lumo 22), Supabase for data, Stripe Checkout + webhooks, SendGrid email, optional AI providers for caption generation.

Please:
1. Map trust boundaries: browser → Flask → Supabase / Stripe / SendGrid / AI APIs.
2. Review authentication, sessions (cookies), and any token-based access (e.g. captions download tokens, magic links).
3. Review Stripe webhook signature verification and idempotency; cron endpoints (e.g. reminders) and shared secrets.
4. Check for common issues: injection, XSS in templates, unsafe redirects, exposure of secrets in client or logs, missing CSRF where relevant, IDOR on order/customer resources.
5. Output: prioritized findings (Critical/High/Medium/Low), each with concrete remediation and file/route hints where you can infer from the repo.
```

### 2.2 API Tester — auth & webhooks

```
Use the API Tester agent.

Focus on Lumo 22’s API routes and webhooks: unauthenticated vs authenticated behaviour, wrong-method responses, predictable tokens, rate limiting gaps, and error messages that might leak internals.

Propose a short manual + automated test checklist (status codes, body shapes, auth failures).
```

### 2.3 Compliance Auditor — privacy (assistive)

```
Use the Compliance Auditor agent.

Compare our stated practices (privacy page, terms, cookie/consent if any) with what the codebase actually does: what PII we collect (email, intake forms, Stripe metadata), where it is stored (Supabase), subprocessors (Stripe, SendGrid, hosting), and retention implied by features.

Flag gaps and inconsistencies only — do not assert legal compliance; recommend “review with counsel” where needed.
```

### 2.4 Consolidated report

```
Combine Security Engineer + API Tester + (if run) Compliance Auditor outputs into one markdown doc with sections:
- Executive summary (top 5 risks)
- Threat model (short)
- Findings table (severity, location, fix)
- Privacy / data handling notes
- Recommended next steps (including non-AI: dependency scan, staging ZAP scan, SECRET_KEY rotation policy)
```

---

## 3. Lumo-specific checklist (for you or the agents)

Use this so reviews don’t miss product-specific surfaces:

| Area | What to verify |
|------|----------------|
| **Sessions** | `SECRET_KEY` set in production; cookie flags (HttpOnly, Secure, SameSite) as deployed |
| **Security headers** | `add_security_headers` in app; HSTS only when HTTPS |
| **Supabase** | RLS policies match “customer sees only own data”; service role not exposed client-side |
| **Stripe** | Webhook secret validated; no trust of client-supplied payment amounts without server verification |
| **Download / magic links** | Tokens unguessable, scoped to order + email, expiry if applicable |
| **Intake / AI** | Intake PII only sent to AI as intended; logs don’t print full payloads or keys |
| **Cron / internal** | `CRON_SECRET` (or equivalent) required for sensitive scheduled routes |
| **`.env` / CI** | No secrets in git; `.env.example` without real values |

---

## 4. Non-agent checks (still do these)

- **Dependencies:** `pip-audit` or GitHub Dependabot on `requirements.txt`
- **Secrets:** periodic scan (e.g. gitleaks) on the repo
- **Staging:** optional OWASP ZAP or similar against a non-production URL
- **Legal:** privacy policy and DPA/subprocessor list with your counsel

---

## 5. Where results usually land

- Single analysis: extend `WEBSITE_TEST_ANALYSIS.md` or add `SECURITY_PRIVACY_REVIEW_YYYY-MM-DD.md`
- Agent test run style: mirror `AGENT_TEST_RUN.md` with a “Security Engineer” subsection
