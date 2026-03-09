# Launch to-do — 30 Days Captions

Single checklist to be ready for go-live.

**Quick check:** Run `python3 scripts/pre_launch_check.py` to verify .env. Add `--live` to ping your deployed site.

---

## Already in place (no action)

- Landing: hero, Captions CTA, trust line
- Captions: product page, pricing, delivery email with branded PDF
- Terms, Privacy, 404
- Nav: Captions, Log in, Sign up
- Footer: Captions, Pricing, Terms, Privacy, Contact
- Account: signup, login, dashboard (manage captions, subscription)
- Emails: order receipt (with product/pricing), intake link, delivery, reminder, welcome/verify, plan change

---

## 1. Config (must-do)

### Railway variables

- [ ] In **Railway** → your service → **Variables**, set:

  | Variable | Note |
  |----------|------|
  | `OPENAI_API_KEY` | Caption generation |
  | `SENDGRID_API_KEY` | All emails |
  | `SUPABASE_URL` | Project URL |
  | `SUPABASE_KEY` | Anon or service role key |
  | `FROM_EMAIL` | e.g. `hello@lumo22.com` — **verified in SendGrid** |
  | `BASE_URL` | Live URL, **no trailing slash** |
  | `STRIPE_SECRET_KEY` | Test or live |
  | `STRIPE_WEBHOOK_SECRET` | From Stripe webhook |
  | `CAPTIONS_PAYMENT_LINK` | Or use Price IDs for Checkout |
  | `STRIPE_CAPTIONS_PRICE_ID` | Captions one-off (required for Checkout) |
  | `STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID` | Optional, for subscription |
  | `CAPTIONS_DELIVER_TEST_SECRET` | Optional; protects test endpoint |

---

## 2. Stripe (must-do)

- [ ] **Success URL** — Captions: `{BASE_URL}/captions-thank-you`
- [ ] **Webhook** — URL = `{BASE_URL}/webhooks/stripe`, events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`
- [ ] **Signing secret** → Railway `STRIPE_WEBHOOK_SECRET`

---

## 3. Content (must-do)

- [ ] **Terms “Last updated”** — Update in `templates/_terms_content.html` if needed
- [ ] **Support inbox** — Confirm `hello@lumo22.com` is the address you’ll use

---

## 4. Testing (must-do before launch)

- [ ] **Captions:** Test payment (one-off or subscription) → thank-you → intake link → submit intake → receive delivery email with PDF
- [ ] **Emails:** Run `python3 scripts/generate_email_samples.py`; open `email_samples/index.html` to preview

---

## 5. Optional

- [ ] **Custom domain** — Point lumo22.com at Railway; set `BASE_URL=https://lumo22.com`
- [ ] **CAPTIONS_DELIVER_TEST_SECRET** — Set in production so `/api/captions-deliver-test` requires `?secret=XXX`
