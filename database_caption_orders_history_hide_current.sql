-- Account → History: hide only the "current" pack row without hiding the whole order or archives.
-- Run in Supabase SQL editor if this column is missing.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS history_hide_current BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN caption_orders.history_hide_current IS
  'When true, History lists delivery_archive rows only; the live latest pack row is hidden. Cleared on next delivery.';
