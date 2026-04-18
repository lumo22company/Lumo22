-- Optional: run in Supabase SQL Editor so customers can dismiss ended subscriptions from
-- Account → Manage subscription → Cancelled subscriptions (hides the row; does not delete order data).

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS resubscribe_prompt_dismissed_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.resubscribe_prompt_dismissed_at IS
  'When set, the customer hid this ended subscription row from Cancelled subscriptions / resubscribe. '
  'Does not remove delivery history or cancel anything in Stripe.';
