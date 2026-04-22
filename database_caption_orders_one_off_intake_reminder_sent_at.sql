-- One-off orders in awaiting_intake: gentle 24–48h reminder email dedupe.
-- Prevents duplicate sends when the daily job runs twice at once (e.g. in-app scheduler + external cron).
ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS one_off_intake_reminder_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.one_off_intake_reminder_sent_at IS
  'When we sent the one-off 24–48h intake reminder for awaiting_intake orders (no subscription). Prevents duplicate sends across parallel workers.';
