-- Add source (campaign attribution) to caption_orders.
-- Captured first-touch from utm_source/utm_medium/utm_campaign (or ?source=/?ref=) on the landing
-- page and carried through the free sample signup and Stripe checkout metadata, so paid orders can
-- be traced back to the campaign that brought them in.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS source TEXT;
COMMENT ON COLUMN caption_orders.source IS 'First-touch campaign attribution, e.g. "google:cpc:us_launch". NULL for direct/unknown traffic and for orders created before this column existed.';

CREATE INDEX IF NOT EXISTS idx_caption_orders_source ON caption_orders(source);
