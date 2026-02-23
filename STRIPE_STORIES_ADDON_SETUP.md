# Stories Add-on Setup

To charge for the 30 Days Story Ideas add-on (+£19 one-off / +£12/mo), do the following.

## 1. Create Stripe products

In Stripe Dashboard → Products:

**Product 1: 30 Days Story Ideas (one-off)**
- Name: `30 Days Story Ideas`
- Description: `One-time add-on: 30 Story prompts for Instagram & Facebook`
- Pricing: One-time, £19 GBP
- Copy the **Price ID** (price_xxx)

**Product 2: 30 Days Story Ideas (subscription)**
- Name: `30 Days Story Ideas — monthly`
- Description: `Monthly add-on: 30 Story prompts each month for Instagram & Facebook`
- Pricing: Recurring, £12/month GBP
- Copy the **Price ID** (price_xxx)

## 2. Add env vars in Railway

```
STRIPE_CAPTIONS_STORIES_PRICE_ID=price_xxx
STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID=price_xxx
```

## 3. Run database migration

In Supabase → SQL Editor, run:

```sql
-- From database_caption_orders_stories.sql
ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS include_stories BOOLEAN NOT NULL DEFAULT FALSE;
```

## 4. Verify

- Visit `/captions`, select Instagram & Facebook as platform
- Stories add-on checkbox should appear
- Select it and proceed to checkout — total should include +£19 (one-off) or +£12/mo (subscription)
- After payment, intake form should show "30 Stories included (already paid)" when applicable
