-- When Stripe sends customer.subscription.deleted, the app clears stripe_subscription_id
-- and sets this timestamp so the account can show Resubscribe vs first-time Upgrade copy.
-- Run in Supabase SQL Editor once.

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS subscription_cancelled_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.subscription_cancelled_at IS 'Set when Stripe subscription ended (webhook deleted); intake row becomes one-off-style for account UI';
