-- Add Stripe customer and subscription IDs to caption_orders (for billing portal)
-- Run in Supabase SQL Editor.

DO $$ BEGIN
    ALTER TABLE caption_orders ADD COLUMN stripe_customer_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE caption_orders ADD COLUMN stripe_subscription_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_caption_orders_stripe_customer ON caption_orders(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
