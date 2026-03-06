-- Add currency to caption_orders (for one-off → subscription flow: subscribe_url preserves currency).
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'gbp';
COMMENT ON COLUMN caption_orders.currency IS 'Payment currency (gbp, usd, eur). Used when building subscribe_url so subscription checkout shows correct currency.';
