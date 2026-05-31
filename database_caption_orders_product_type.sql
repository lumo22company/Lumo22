-- Free 3-caption sample packs (no Stripe). Run in Supabase SQL Editor on production.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS product_type TEXT NOT NULL DEFAULT 'standard';

COMMENT ON COLUMN caption_orders.product_type IS 'standard = paid 30-day pack; sample_3 = free 3-caption snapshot';

CREATE INDEX IF NOT EXISTS idx_caption_orders_product_type_email_created
  ON caption_orders (customer_email, product_type, created_at DESC)
  WHERE product_type = 'sample_3';
