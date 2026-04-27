-- (E) After switching production from Stripe test to live, clear cached promotion code ids.
-- Test-mode prom_ ids stored in customers.stripe_referral_promotion_code_id are invalid against live keys.
-- After this UPDATE, each affected referrer should load Account once (or open Refer a friend) so
-- ensure_stripe_promotion_code_for_customer creates and stores a live promotion code.
--
-- Preview before running (optional):
-- SELECT id, email, stripe_referral_promotion_code_id FROM public.customers
--   WHERE stripe_referral_promotion_code_id IS NOT NULL;

UPDATE public.customers
SET stripe_referral_promotion_code_id = NULL
WHERE stripe_referral_promotion_code_id IS NOT NULL;
