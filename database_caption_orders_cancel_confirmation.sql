-- One cancellation confirmation email per subscription lifecycle (dedupe updated + deleted webhooks).
-- Run in Supabase SQL Editor once.

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS cancel_confirmation_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.cancel_confirmation_sent_at IS 'Set when subscription cancel confirmation email was sent; cleared when customer resumes subscription (cancel_at_period_end cleared)';
