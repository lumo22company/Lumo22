-- Cross-worker dedupe: upgrade + "Get first pack now" schedules delivery from both Stripe webhook
-- and thank-you /captions-intake-link polling. In-memory dedupe does not span Gunicorn workers.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS immediate_pack_dispatch_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.immediate_pack_dispatch_at IS
  'Set once when an immediate subscription pack delivery is dispatched (upgrade get-pack-now). '
  'Null = not yet claimed; used to dedupe webhook vs thank-you API across workers. '
  'Cleared when order moves to failed so retries can claim again.';
