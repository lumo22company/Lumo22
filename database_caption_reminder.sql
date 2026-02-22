-- Subscription reminder: track when we sent a reminder for each billing period.
-- Opt-out: customers can disable these emails (default: on).
-- Run in Supabase SQL Editor.

DO $$ BEGIN
  ALTER TABLE caption_orders ADD COLUMN reminder_sent_period_end TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN caption_orders.reminder_sent_period_end IS 'When we sent the pre-pack reminder for this billing period (Stripe current_period_end). Prevents duplicate reminders.';

DO $$ BEGIN
  ALTER TABLE caption_orders ADD COLUMN reminder_opt_out BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN caption_orders.reminder_opt_out IS 'If true, do not send pre-pack reminder emails. Default: false (opt-out, reminders on).';
