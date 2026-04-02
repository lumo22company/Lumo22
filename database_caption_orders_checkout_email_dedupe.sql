-- Prevent duplicate caption_orders rows for the same Stripe Checkout session (webhook vs thank-you API race).
-- Prevents two post-checkout confirmation emails. Run in Supabase SQL Editor.
--
-- If index creation fails due to existing duplicates, fix first, e.g.:
--   SELECT stripe_session_id, count(*) FROM caption_orders WHERE stripe_session_id IS NOT NULL
--     AND trim(stripe_session_id) <> '' GROUP BY 1 HAVING count(*) > 1;

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS checkout_confirmation_email_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.checkout_confirmation_email_sent_at IS
  'Set when order-confirmed + intake (or upgrade welcome) email was sent; used to dedupe across webhook and API.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_caption_orders_stripe_session_id_unique
  ON caption_orders (stripe_session_id)
  WHERE stripe_session_id IS NOT NULL AND length(trim(stripe_session_id)) > 0;
