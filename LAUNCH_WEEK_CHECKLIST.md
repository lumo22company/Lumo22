# Launch week — do these in order

One place for everything you need to do before go-live. Copy-paste values where possible.

**Quick check:** Run `python3 scripts/pre_launch_check.py` to verify .env. Add `--live` to also ping your deployed site.

---

## 1. Railway variables (2 min)

**Railway** → your project → **Lumo 22** service → **Variables**.

Confirm these exist (add any missing):

| Variable | Example / note |
|----------|----------------|
| `OPENAI_API_KEY` | sk-proj-... |
| `SENDGRID_API_KEY` | SG.... |
| `SUPABASE_URL` | https://....supabase.co |
| `SUPABASE_KEY` | eyJ... |
| `FROM_EMAIL` | hello@lumo22.com |
| `BASE_URL` | `https://lumo-22-production.up.railway.app` (or `https://lumo22.com` if custom domain is live) — **no trailing slash** |
| `CHAT_PAYMENT_LINK` | https://buy.stripe.com/... |
| `ACTIVATION_LINK_STARTER` | https://buy.stripe.com/... |
| `ACTIVATION_LINK_STANDARD` | https://buy.stripe.com/... |
| `ACTIVATION_LINK_PREMIUM` | https://buy.stripe.com/... |
| `STRIPE_SECRET_KEY` | sk_test_... or sk_live_... |
| `STRIPE_WEBHOOK_SECRET` | whsec_... |
| `STRIPE_CAPTIONS_PRICE_ID` | price_... |
| `STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID` | price_... |

Optional: `ACTIVATION_LINK_STARTER_BUNDLE`, `ACTIVATION_LINK_STANDARD_BUNDLE`, `ACTIVATION_LINK_PREMIUM_BUNDLE`.

---

## 2. SendGrid Inbound Parse (2 min)

1. Go to **SendGrid** → [app.sendgrid.com](https://app.sendgrid.com) → **Settings** → **Inbound Parse**.
2. **Add Host & URL**.
3. Paste:

   - **Destination URL:** `{BASE_URL}/webhooks/sendgrid-inbound` (e.g. `https://lumo22.com/webhooks/sendgrid-inbound`)
   - **Domain:** `inbound.lumo22.com`

4. Save.

---

## 3. DNS — MX record (2 min)

Where **lumo22.com** DNS is managed (e.g. GoDaddy → My Products → lumo22.com → **DNS**):

**Add record:**

| Field | Value |
|-------|--------|
| **Type** | MX |
| **Name / Host** | `inbound` |
| **Value / Points to** | `mx.sendgrid.net` |
| **Priority** | `10` |
| **TTL** | 3600 (or default) |

Save. Propagation can take 5–15 minutes (up to 48 hours).

---

## 4. Stripe — Success URLs on payment links (5 min)

In **Stripe** → **Product catalog** (or **Payment links**) → open **each** payment link:

- **Front Desk (Starter, Growth, Pro) and Bundles:** After payment → **Redirect** = `{BASE_URL}/activate-success` (e.g. `https://lumo22.com/activate-success`)
- **Chat only (£59):** Redirect = `{BASE_URL}/website-chat-success`
- **Captions one-off (£97):** Redirect = `{BASE_URL}/captions-thank-you`
- **Captions subscription (£79/mo):** Set in Checkout session (app sets it from BASE_URL) — ensure Railway `BASE_URL` has no trailing slash.

If you use a custom domain (lumo22.com pointing to Railway), use `https://lumo22.com` instead of the Railway URL above.

---

## 5. Stripe — Webhook (2 min)

**Stripe** → **Developers** → **Webhooks** → your endpoint (or Add endpoint):

- **Endpoint URL:** `{BASE_URL}/webhooks/stripe` (e.g. `https://lumo22.com/webhooks/stripe`)
- **Events:** include `checkout.session.completed`.
- **Signing secret** → copy to Railway as `STRIPE_WEBHOOK_SECRET`.

---

## 6. Quick tests (you do these)

- [ ] **Front Desk:** Pay with test card (Starter/Growth/Pro) → complete setup form → you get email with `reply-xxxxx@inbound.lumo22.com` → send an email to that address → you receive an auto-reply.
- [ ] **Chat £59:** Pay → redirect to website-chat-success → you get setup email → open link, submit form → you see embed code.
- [ ] **Captions:** Pay (subscription or one-off) → thank-you page → intake link (from email or redirect) → submit intake → you get delivery email (or confirm intake is received).

---

## 7. Contact & terms

- [ ] **hello@lumo22.com** is the support inbox and is a **verified sender** in SendGrid.
- [ ] Terms “Last updated” is correct in `templates/_terms_content.html` (currently February 2025).

---

**When 1–5 and 7 are done and 6 passes, you’re ready to launch.**

Optional later: custom domain (lumo22.com → Railway), live Stripe keys, real chat widget.
