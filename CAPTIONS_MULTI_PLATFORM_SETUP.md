# 30 Days Captions — Multi-platform add-on setup

Extra platforms are charged at **£29 one-off** or **£19/month** per platform (2nd, 3rd, etc.). Base price covers 1 platform. Platforms are chosen at checkout and prefilled on the intake form.

## 1. Database

Run in Supabase SQL Editor:

```sql
-- From database_caption_orders_platforms.sql
ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS platforms_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS selected_platforms TEXT;
```

## 2. Stripe prices for add-on

From project root:

```bash
python3 scripts/create_captions_extra_platform_prices.py
```

Add the printed env vars to `.env` and Railway:

- `STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID` (one-off £29)
- `STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID` (£19/month)

## 3. Flow

- **Product page** (`/captions`): Customer chooses “How many platforms?” (1–5). Price and CTAs update (e.g. 3 platforms → £155 one-off, £117/mo).
- **Checkout**: Same totals; “Next step” goes to Stripe with the correct line items (base + add-on quantity).
- **Webhook**: Reads `metadata.platforms` from the session and stores `platforms_count` on the order.
- **Intake**: Platform(s) are **prefilled** from `order.selected_platforms` (chosen at checkout). If `platforms_count > 1`, checkboxes are prefilled; otherwise the single platform dropdown is prefilled.

If the two add-on price IDs are not set, only 1-platform checkouts work (no add-on line item). Existing one-off £97 and subscription £79 flows are unchanged when the customer leaves “1 platform” selected.
