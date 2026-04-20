-- Track the one-time "complete your intake" email for new subscribers (~2h after checkout).
-- Run in Supabase SQL Editor after deploy.

DO $$ BEGIN
  ALTER TABLE caption_orders ADD COLUMN intake_early_reminder_sent_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN caption_orders.intake_early_reminder_sent_at IS 'When we sent the 2h post-checkout intake reminder for subscription orders still awaiting_intake. Prevents duplicate sends.';
