# Launch readiness — 30 Days Captions

What’s in place and what’s left to do before going live.

---

## 1. What’s in place

### Website & pages
- **Landing page** (`/`) — Hero, Captions CTA, footer
- **30 Days Captions** (`/captions`) — Product page, pricing, Get my 30 days / Subscribe CTAs
- **Checkout** — One-off and subscription flows; redirect to thank-you
- **Thank-you** — Links to intake form
- **Intake** (`/captions-intake`) — Form for business details, voice, platforms
- **Terms** (`/terms`), **Privacy** (`/privacy`)
- **Account** — Login, signup, dashboard (manage captions, subscription)
- **404** — Custom not-found page
- **Nav/footer** — Captions, Pricing, Terms, Privacy, Contact

### 30 Days Captions flow
- Stripe: one-off (£97) and subscription (£79/mo) payment links + Checkout
- After payment: webhook sends order receipt (with product/pricing) + intake link
- Intake form: customer fills details → generation starts
- Delivery: email with branded PDF (and optional Story Ideas PDF)
- Subscription renewals: `invoice.paid` webhook → regenerate + deliver new pack
- Reminder emails: ~5 days before renewal, link to update form

### Technical
- **Railway** — Deploys from repo; env vars for Stripe, SendGrid, Supabase, OpenAI, BASE_URL
- **Stripe webhook** — Events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `invoice.created` (referral)
- **Emails** — Order receipt, intake link, delivery, reminder, welcome/verify, password reset, plan change

---

## 2. What you have left to do

### Must-do before launch (config)
- [ ] **Railway variables** — Set: `OPENAI_API_KEY`, `SENDGRID_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `FROM_EMAIL`, `BASE_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `CAPTIONS_PAYMENT_LINK` (or Stripe Price IDs for Checkout)
- [ ] **BASE_URL** — No trailing slash; e.g. `https://lumo22.com` or your Railway URL
- [ ] **FROM_EMAIL** — Must be verified in SendGrid (e.g. `hello@lumo22.com`)
- [ ] **CAPTIONS_DELIVER_TEST_SECRET** — Optional; if set, protects `/api/captions-deliver-test` (use `?secret=XXX`)

### Stripe
- [ ] **Success URL** — Captions one-off/subscription → `{BASE_URL}/captions-thank-you`
- [ ] **Webhook** — URL = `{BASE_URL}/webhooks/stripe`, events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`
- [ ] **Signing secret** → Railway `STRIPE_WEBHOOK_SECRET`

### Content
- [ ] **Terms date** — `templates/_terms_content.html` “Last updated” matches go-live
- [ ] **Contact** — Confirm `hello@lumo22.com` is the support inbox

### Testing
- [ ] **Captions** — Test payment (one-off or subscription) → thank-you → intake link → submit form → receive delivery email with PDF
- [ ] **Emails** — Run `python3 scripts/generate_email_samples.py` and check `email_samples/index.html`

---

## 3. Quick checklist

| # | Task | Done |
|---|------|------|
| 1 | Railway: env vars (Stripe, SendGrid, Supabase, OpenAI, FROM_EMAIL, BASE_URL) | |
| 2 | Stripe: Success URL = `{BASE_URL}/captions-thank-you` | |
| 3 | Stripe: Webhook URL = `{BASE_URL}/webhooks/stripe`, events above | |
| 4 | SendGrid: FROM_EMAIL verified | |
| 5 | Test: Captions payment → intake → delivery email | |
| 6 | Terms date + contact email correct | |

---

## 4. Where to look

- **Captions setup:** `CAPTIONS_GO_LIVE_CHECKLIST.md`
- **Deploy:** `DEPLOY_TO_LIVE.md`
- **Troubleshooting:** `NOT_RECEIVING_EMAIL_AFTER_CHECKOUT.md`, `WHY_NO_INTAKE_EMAIL.md`
