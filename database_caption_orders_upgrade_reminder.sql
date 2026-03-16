-- One-off upgrade reminder: track when we sent the email and allow opt-out.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS upgrade_reminder_sent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS upgrade_reminder_opt_out BOOLEAN DEFAULT false;

COMMENT ON COLUMN caption_orders.upgrade_reminder_sent_at IS 'When we sent the one-off → subscription upgrade reminder email (once per order).';
COMMENT ON COLUMN caption_orders.upgrade_reminder_opt_out IS 'If true, do not send one-off upgrade reminder to this order.';
