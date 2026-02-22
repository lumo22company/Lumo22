# Launch to-do — one list to be ready for go-live

Use this as your single checklist. Tick each item when it’s done.

**Done:** Pre-launch check run (passed); login/signup template links fixed (`/business/signup` → `/signup`, `/business/login` → `/login`).

**Quick check:** Run `python3 scripts/pre_launch_check.py` to verify .env. Add `--live` to ping your deployed site.

---

## Already in place (no action)

- Landing: hero subline, stronger split copy, final CTA section, trust line
- Captions: value line; delivery email sends **branded PDF** (Lumo 22 logo, gold/black)
- Terms: “Last updated: February 2025” in `_terms_content.html`
- Contact: `hello@lumo22.com` used across site and in code
- Nav: Captions, Front Desk, Pricing, Sign up / Log in

---

## 1. Config & infra (must-do)

### Railway variables

- [ ] In **Railway** → your project → **Lumo 22** service → **Variables**, confirm all set:

  | Variable | Note |
  |----------|------|
  | `OPENAI_API_KEY` | For caption generation |
  | `SENDGRID_API_KEY` | For all emails |
  | `SUPABASE_URL` | Supabase project URL |
  | `SUPABASE_KEY` | Service role or anon key (as used by app) |
  | `FROM_EMAIL` | e.g. `hello@lumo22.com` — **must be verified in SendGrid** |
  | `BASE_URL` | Your live URL, **no trailing slash** (e.g. `https://lumo22.com` or Railway URL) |
  | `STRIPE_SECRET_KEY` | Test or live |
  | `STRIPE_WEBHOOK_SECRET` | From Stripe webhook |
  | `STRIPE_CAPTIONS_PRICE_ID` | Captions one-off |
  | `STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID` | Captions subscription (if used) |
  | `CHAT_PAYMENT_LINK` | Chat £59 |
  | `ACTIVATION_LINK_STARTER` | Front Desk Starter |
  | `ACTIVATION_LINK_STANDARD` | Front Desk Standard |
  | `ACTIVATION_LINK_PREMIUM` | Front Desk Premium |

- [ ] Optional: `ACTIVATION_LINK_*_BUNDLE` if you use bundles.

### SendGrid

- [ ] **hello@lumo22.com** (or whatever `FROM_EMAIL` is) is a **verified sender** in SendGrid.
- [ ] **Inbound Parse** set: host `inbound.lumo22.com` → URL = `{BASE_URL}/webhooks/sendgrid-inbound`.

### DNS (for Front Desk auto-reply)

- [ ] **MX record** for `inbound.lumo22.com` → `mx.sendgrid.net`, priority `10` (wherever lumo22.com DNS is managed).

---

## 2. Stripe (must-do)

### Payment link success URLs

- [ ] **Front Desk** (Starter / Standard / Premium) and **bundles:** redirect = `{BASE_URL}/activate-success`
- [ ] **Chat only (£59):** redirect = `{BASE_URL}/website-chat-success`
- [ ] **Captions one-off (£97):** redirect = `{BASE_URL}/captions-thank-you`
- [ ] **Captions subscription:** app uses `BASE_URL` for Checkout success URL — just ensure `BASE_URL` in Railway is correct (no trailing slash).

### Webhook

- [ ] **Stripe** → Developers → Webhooks → endpoint URL = `{BASE_URL}/webhooks/stripe`
- [ ] Events include **checkout.session.completed**
- [ ] **Signing secret** copied to Railway as `STRIPE_WEBHOOK_SECRET`

---

## 3. Content & legal (must-do)

- [ ] **Terms “Last updated”** — If your go-live date is not February 2025, update in `templates/_terms_content.html` (first line).
- [ ] **Support inbox** — You’re happy that `hello@lumo22.com` is the address you’ll use for support and that you’ll check it.

---

## 4. Testing (must-do before launch)

- [ ] **Digital Front Desk:** Test payment (e.g. Starter) → complete setup form → receive email with `reply-xxxxx@inbound.lumo22.com` → send an email to that address → you get an auto-reply.
- [ ] **Chat £59:** Test payment → redirect to website-chat-success → receive setup email → open link, submit form → see embed code (widget can be placeholder).
- [ ] **Captions:** Test payment (one-off or subscription) → thank-you page → open intake link (from email or redirect) → submit intake → receive **delivery email with PDF** (branded 30 Days Captions).
- [ ] **Captions PDF:** Open the PDF from the test delivery and confirm logo, gold headings, and readability.

---

## 5. Fixes / polish (do if any apply)

- [ ] **Broken links** — Click through every nav and footer link on the live site; fix any 404s or wrong URLs.
- [ ] **Spam folder** — After tests, check that delivery and intake emails don’t land in spam; follow SendGrid best practice (e.g. **SENDGRID_INBOX_NOT_SPAM.md** if you have it).
- [ ] **Webhook errors** — If any Stripe or SendGrid webhook fails, check Railway logs and **WHERE_TO_SEE_WEBHOOK_ERROR.md** (or Stripe webhook dashboard) and fix the cause.

---

## 6. Optional before launch

- [ ] **Custom domain** — Point lumo22.com at Railway, then set `BASE_URL=https://lumo22.com` and update Stripe webhook + payment link success URLs to use lumo22.com.
- [ ] **Signup/Login** — If you’re not using the account/dashboard for launch, you can leave as-is or hide from nav later.
- [ ] **Chat widget** — Currently a placeholder; safe to launch and add live chat later.

---

## 7. When you’re ready for real payments

- [ ] **Stripe live mode** — Create live payment links and (if needed) a live webhook; put live keys and webhook secret in Railway.
- [ ] **BASE_URL** — If you use a custom domain, keep `BASE_URL=https://lumo22.com` (or your live domain) so all emails and redirects use it.

---

## Summary

**Must-do to launch:**  
Sections **1** (Railway + SendGrid + DNS), **2** (Stripe URLs + webhook), **3** (terms + inbox), and **4** (all three product tests passing).

**When 1–4 are done and tests pass, you’re ready to go live.**

For more detail on any step, see **LAUNCH_WEEK_CHECKLIST.md** or **LAUNCH_READINESS.md**.
