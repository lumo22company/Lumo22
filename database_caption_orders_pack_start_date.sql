-- Persist calendar Day 1 chosen at intake save (aligned with validation + PDF generation).
-- Cleared after each successful delivery so renewals without a fresh edit do not keep a stale anchor.
-- Run in Supabase SQL editor if this column is missing.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS pack_start_date DATE;

COMMENT ON COLUMN caption_orders.pack_start_date IS
  'Inclusive first day of the 30-day captions window for this pack (YYYY-MM-DD, UTC). Set when intake is saved/updated; cleared on delivery.';
