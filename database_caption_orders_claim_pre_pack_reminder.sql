-- Pre-pack reminder (run_reminders): dedupe when the daily job runs twice at once (scheduler + cron).
-- Atomically sets reminder_sent_period_end to the Stripe current_period_end anchor for this send only if
-- the row does not already hold that value (or it is null). Returns true if this caller should send.
-- Run in Supabase SQL Editor after caption_orders exists.

CREATE OR REPLACE FUNCTION public.claim_pre_pack_reminder(p_order_id uuid, p_period_end timestamptz)
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
    reminder_sent_period_end = p_period_end,
    updated_at = now()
  WHERE id = p_order_id
    AND (
      reminder_sent_period_end IS NULL
      OR reminder_sent_period_end IS DISTINCT FROM p_period_end
    );
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END;
$$;

COMMENT ON FUNCTION public.claim_pre_pack_reminder(uuid, timestamptz) IS
  'Atomically records reminder_sent_period_end for this billing period; returns true if this worker should send the pre-pack reminder email.';

REVOKE ALL ON FUNCTION public.claim_pre_pack_reminder(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_pre_pack_reminder(uuid, timestamptz) TO service_role;
