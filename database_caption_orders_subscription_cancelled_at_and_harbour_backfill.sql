-- Run once in Supabase → SQL Editor (paste all, Run).
-- Adds subscription_cancelled_at if missing, then backfills Harbour & Hearth cancelled sub row
-- so Edit form shows "Former subscription" / Resubscribe (see app _order_is_former_subscription_row).
--
-- Local DATABASE_URL auth failed from CI/agent — use the dashboard for DDL.

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS subscription_cancelled_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.subscription_cancelled_at IS 'Set when Stripe subscription ended (webhook deleted); intake row becomes one-off-style for account UI';

-- Harbour & Hearth (order that received cancel email; stripe_subscription_id already cleared by webhook)
UPDATE caption_orders
SET subscription_cancelled_at = COALESCE(
    subscription_cancelled_at,
    '2026-03-30T16:00:00+00:00'::timestamptz
)
WHERE id = 'b56e249a-442f-4650-82b0-f3101f89fba1'
  AND trim(coalesce(intake->>'business_name', '')) = 'Harbour & Hearth';
