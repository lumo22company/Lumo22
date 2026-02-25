-- Add pack_history to caption_orders for subscription variety (avoid repetitive content month on month).
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS pack_history JSONB NOT NULL DEFAULT '[]';

COMMENT ON COLUMN caption_orders.pack_history IS 'For subscriptions: list of {month, day_categories} for each delivered pack. Used to vary categories month on month.';
