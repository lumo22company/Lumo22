-- Add platforms_count and selected_platforms to caption_orders.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS platforms_count INTEGER NOT NULL DEFAULT 1;
COMMENT ON COLUMN caption_orders.platforms_count IS 'Number of platforms included in order (1 = base price, 2+ = base + extra platform add-ons).';

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS selected_platforms TEXT;
COMMENT ON COLUMN caption_orders.selected_platforms IS 'Comma-separated platforms chosen at checkout (e.g. Instagram, LinkedIn). Prefilled on intake form.';
