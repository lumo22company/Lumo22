-- Add include_stories to caption_orders (paid at checkout for Stories add-on).
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS include_stories BOOLEAN NOT NULL DEFAULT FALSE;
COMMENT ON COLUMN caption_orders.include_stories IS 'True when customer paid for 30 Days Story Ideas add-on at checkout. Passed to order from Stripe metadata.';
