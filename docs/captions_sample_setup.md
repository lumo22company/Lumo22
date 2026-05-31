# Free 3-caption sample (`/captions-sample`)

## What you need to do

### 1. Run Supabase migration (production)

In the **Supabase SQL editor**, run:

`database_caption_orders_product_type.sql`

This adds `product_type` (`standard` | `sample_3`) on `caption_orders`.

### 2. Deploy the app

Commit and deploy to Railway (or your usual path) so these routes are live:

- `GET /captions-sample` — signup page
- `POST /api/captions-sample/start` — creates order + sends intake email
- Existing `GET /captions-intake?t=…` — same form, sample mode when `product_type = sample_3`

Requires **SendGrid** + **AI provider** (same as paid packs).

### 3. Test once on production

1. Open https://www.lumo22.com/captions-sample
2. Use a test email you control
3. Complete the intake link from email
4. Confirm 3 captions arrive by email with upgrade link to `/captions`

### 4. Point cold email to the sample URL

In Smartlead **email 1**, change the main CTA link from `/captions` to:

`https://www.lumo22.com/captions-sample`

Keep the one-off line in copy (“no subscription needed”) — the sample page reinforces that.

### 5. Optional: Smartlead / ops (parallel)

- Fix mailbox daily limits and send window (Bath/Bristol)
- Re-enable warmup if needed
- Resume leads paused by auto-replies

## Behaviour

- **Rate limit:** one sample per email, **ever** (including if they never completed the form)
- **No Stripe** — order row has `product_type = sample_3`
- **Delivery:** email body (markdown), not a PDF
- **Upgrade CTA:** links to `/captions`

## Banner

`/captions` hero includes: “Get 3 free sample captions — no card required” → `/captions-sample`
