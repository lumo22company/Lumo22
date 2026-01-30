# 30 Days Captions — Automation Setup

The offer is automated end-to-end: **payment → intake email → client fills form → AI generates 30 captions → delivery email with attachment.**

---

## Flow

1. **Customer pays** (Stripe Payment Link for £97).
2. **Stripe webhook** (`POST /webhooks/stripe`) runs: creates a `caption_orders` row with a unique token, sends the client an email with link `{BASE_URL}/captions-intake?t={token}`.
3. **Client opens link**, fills the intake form, clicks "Send my answers".
4. **POST /api/captions-intake** saves intake and starts a background thread that:
   - Calls OpenAI to generate 30 captions from the framework + intake.
   - Saves the markdown to the order and sets status `delivered`.
   - Emails the client with the `.md` file attached.
5. Client receives the captions by email within a few minutes.

---

## What you need

- **Supabase:** Table `caption_orders` (run `database_caption_orders.sql` in SQL Editor).
- **Stripe:** Payment link for £97; webhook endpoint pointing at your app.
- **SendGrid:** So the app can send intake-link and delivery emails.
- **OpenAI:** So the app can generate captions (uses `OPENAI_MODEL` from config).
- **Env:** `STRIPE_WEBHOOK_SECRET`, `BASE_URL`, and optionally `STRIPE_CAPTIONS_PRICE_ID`.

---

## 1. Database

In Supabase → SQL Editor, run the contents of **`database_caption_orders.sql`** (in the project root). That creates the `caption_orders` table and indexes.

---

## 2. Stripe

1. Create the product and payment link (see `STEPS_TO_SELL_30_DAYS_CAPTIONS.md`).
2. Set the payment link’s **After payment** redirect to: `https://yourdomain.com/captions-thank-you`.
3. Add a webhook:
   - Dashboard → **Developers** → **Webhooks** → **Add endpoint**.
   - **Endpoint URL:** `https://yourdomain.com/webhooks/stripe`.
   - **Events:** `checkout.session.completed`.
   - Save and copy the **Signing secret** (`whsec_...`).
4. In `.env` set:
   - `STRIPE_WEBHOOK_SECRET=whsec_...`
   - `BASE_URL=https://yourdomain.com`
   - Optionally `STRIPE_CAPTIONS_PRICE_ID=price_xxxx` if you want to only treat that price as “captions” (otherwise any £97 payment is treated as captions).

---

## 3. Environment

Ensure these are set (see `.env.example`):

- `CAPTIONS_PAYMENT_LINK` — Stripe payment link URL.
- `STRIPE_WEBHOOK_SECRET` — From the webhook you added.
- `BASE_URL` — Your site’s base URL (no trailing slash).
- `SENDGRID_API_KEY` and `FROM_EMAIL` — For sending emails.
- `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) — For caption generation.
- `SUPABASE_URL` and `SUPABASE_KEY` — For `caption_orders`.

---

## 4. Deploy / run

- App must be reachable at `BASE_URL` so Stripe can call `/webhooks/stripe` and clients can open `/captions-intake?t=...`.
- Restart the app after changing env vars.

---

## Testing

1. **Webhook:** Use Stripe Dashboard → Developers → Webhooks → your endpoint → **Send test webhook** → `checkout.session.completed`. Or do a real test purchase in test mode; the webhook should create an order and send the intake email (from `FROM_EMAIL`) to the customer email on the session.
2. **Intake:** Open the intake link from that email, fill the form, submit. Check that you receive the delivery email with the markdown attachment.
3. **Orders:** In Supabase, check `caption_orders` for statuses `awaiting_intake`, `intake_completed`, `generating`, `delivered`, or `failed`.

---

## If something breaks

- **No intake email:** Check Stripe webhook is receiving `checkout.session.completed`, that `_is_captions_payment` is true (amount or metadata), and that SendGrid is configured and not throttling.
- **Intake form says "Invalid or expired link":** The token in the URL must match an existing order; check `caption_orders` and that the link was not altered.
- **No delivery email:** Check app logs for errors in the background thread (OpenAI or SendGrid). Check `caption_orders.status` for `failed` and fix the cause (e.g. model, token limit, or email).
- **Stripe signature error:** Ensure `STRIPE_WEBHOOK_SECRET` matches the webhook’s signing secret and that the raw body is used for verification (Flask’s `request.get_data()` is correct).
