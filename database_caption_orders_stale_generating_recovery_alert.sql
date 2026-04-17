-- Dedupe ops email when recovery cron starts a thread for the same stuck "generating" order.
-- Without this, multiple Railway workers each send "Stuck generating — recovery started" (in-memory throttle is per-process).
-- Run in Supabase SQL Editor after your main caption_orders schema exists.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS stale_generating_recovery_alert_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.stale_generating_recovery_alert_sent_at IS
  'When we last emailed INTERNAL_ALERT_EMAIL about stale generating recovery for this row; '
  'claim_stale_generating_recovery_alert() uses it with a cooldown so parallel workers do not duplicate the same alert.';

CREATE OR REPLACE FUNCTION public.claim_stale_generating_recovery_alert(p_order_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n int;
BEGIN
  UPDATE caption_orders
  SET
    stale_generating_recovery_alert_sent_at = now(),
    updated_at = now()
  WHERE id = p_order_id
    AND lower(trim(status)) = 'generating'
    AND (
      stale_generating_recovery_alert_sent_at IS NULL
      OR stale_generating_recovery_alert_sent_at < now() - interval '4 hours'
    );
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END;
$$;

COMMENT ON FUNCTION public.claim_stale_generating_recovery_alert(uuid) IS
  'Atomically records that stale-generating recovery may send the ops alert; returns true if this caller should send.';

REVOKE ALL ON FUNCTION public.claim_stale_generating_recovery_alert(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_stale_generating_recovery_alert(uuid) TO service_role;
