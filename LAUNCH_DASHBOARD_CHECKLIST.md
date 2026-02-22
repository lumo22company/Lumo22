# Launch — dashboard checklist (do these yourself)

These can’t be done from code. Tick each when done.

---

## Railway (Variables)

In **Railway** → your project → **Lumo 22** service → **Variables**, confirm:

| Variable | Note |
|----------|------|
| `OPENAI_API_KEY` | Caption generation |
| `SENDGRID_API_KEY` | All emails |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Service role or anon key |
| `FROM_EMAIL` | e.g. `hello@lumo22.com` — **must be verified in SendGrid** |
| `BASE_URL` | Live URL, **no trailing slash** (e.g. `https://lumo-22-production.up.railway.app`) |
| `STRIPE_SECRET_KEY` | Test or live |
| `STRIPE_WEBHOOK_SECRET` | From Stripe webhook |
| `STRIPE_CAPTIONS_PRICE_ID` | Captions one-off |
| `STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID` | If used |
| `CHAT_PAYMENT_LINK` | Chat £59 |
| `ACTIVATION_LINK_STARTER` | Front Desk Starter |
| `ACTIVATION_LINK_STANDARD` | Front Desk Standard |
| `ACTIVATION_LINK_PREMIUM` | Front Desk Premium |

---

## SendGrid

- [ ] **FROM_EMAIL** (e.g. hello@lumo22.com) is a **verified sender** in SendGrid.
- [ ] **Inbound Parse** (if using Front Desk): host `inbound.lumo22.com` → URL = `{BASE_URL}/webhooks/sendgrid-inbound`.

---

## DNS (for Front Desk auto-reply)

- [ ] **MX record** for `inbound.lumo22.com` → `mx.sendgrid.net`, priority `10`.

---

## Stripe

### Payment link success URLs

- [ ] **Front Desk** (Starter / Standard / Premium): redirect = `{BASE_URL}/activate-success`
- [ ] **Chat only (£59):** redirect = `{BASE_URL}/website-chat-success`
- [ ] **Captions one-off (£97):** redirect = `{BASE_URL}/captions-thank-you`
- [ ] **Captions subscription:** app uses `BASE_URL`; ensure `BASE_URL` in Railway is correct.

### Webhook

- [ ] **Stripe** → Developers → Webhooks → URL = `{BASE_URL}/webhooks/stripe`
- [ ] Events include **checkout.session.completed**
- [ ] **Signing secret** copied to Railway as `STRIPE_WEBHOOK_SECRET`

---

## Optional

- [ ] **Terms** — If go-live isn’t Feb 2025, update “Last updated” in `templates/_terms_content.html`.
- [ ] **Custom domain** — Point lumo22.com at Railway, set `BASE_URL=https://lumo22.com`, update Stripe webhook + success URLs.

---

*When 1–4 are done and your product tests pass, you’re ready to go live.*
