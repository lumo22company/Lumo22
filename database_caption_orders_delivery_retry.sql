-- Auto-retry and visibility for first-pack caption delivery failures
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS delivery_failure_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS delivery_last_error TEXT;

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS delivery_last_attempt_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.delivery_failure_count IS
'Increments on each failed generation/delivery attempt; auto-retry stops when >= 3.';

COMMENT ON COLUMN caption_orders.delivery_last_error IS
'Last delivery/generation error message (truncated) for support and health checks.';

COMMENT ON COLUMN caption_orders.delivery_last_attempt_at IS
'Timestamp of last attempted generation/delivery run.';
