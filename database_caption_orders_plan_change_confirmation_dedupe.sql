-- Plan-change confirmation email: cross-process dedupe for Stripe subscription.updated + billing API.
-- Same signature within 1 hour = one send (replaces in-memory dict in webhook worker).
-- Run in Supabase SQL Editor after caption_orders exists.

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS plan_change_confirmation_signature TEXT;

ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS plan_change_confirmation_sent_at TIMESTAMPTZ;

COMMENT ON COLUMN caption_orders.plan_change_confirmation_signature IS
  'Last plan-change confirmation dedupe key (sub|email|platforms|stories); paired with sent_at.';

COMMENT ON COLUMN caption_orders.plan_change_confirmation_sent_at IS
  'When we claimed/sent the plan-change confirmation for the current signature; used to suppress duplicate webhooks within 1 hour.';


CREATE OR REPLACE FUNCTION public.claim_plan_change_confirmation(p_order_id uuid, p_signature text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n int;
BEGIN
  IF p_signature IS NULL OR btrim(p_signature) = '' THEN
    RETURN false;
  END IF;

  UPDATE caption_orders
  SET
    plan_change_confirmation_signature = p_signature,
    plan_change_confirmation_sent_at = now(),
    updated_at = now()
  WHERE id = p_order_id
    AND (
      plan_change_confirmation_signature IS DISTINCT FROM p_signature
      OR plan_change_confirmation_sent_at IS NULL
      OR plan_change_confirmation_sent_at < now() - interval '1 hour'
    );

  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END;
$$;

COMMENT ON FUNCTION public.claim_plan_change_confirmation(uuid, text) IS
  'Atomically records plan-change confirmation dedupe for this order+signature; returns true if this caller should send email.';

REVOKE ALL ON FUNCTION public.claim_plan_change_confirmation(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_plan_change_confirmation(uuid, text) TO service_role;
