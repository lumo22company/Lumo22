-- One-time customer email when caption auto-recovery picks up an order stuck in status=generating
-- (deduped via claim before send). Run in Supabase SQL Editor after your main caption_orders schema exists.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS generating_stuck_customer_notified_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.generating_stuck_customer_notified_at IS
  'Set when the app sends the one-time "pack taking longer than usual" customer email during stale-generating recovery; '
  'cleared on successful delivery (set_delivered) so a future stuck episode can notify again.';
