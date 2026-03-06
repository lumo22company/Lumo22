-- Add explicit RLS policies so Supabase no longer reports "RLS enabled but no policies exist".
-- Both tables are only accessed by the backend using the service_role key (which bypasses RLS).
-- These policies deny anon and authenticated any access; service_role is unaffected.
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).

-- ========== public.appointments ==========
DROP POLICY IF EXISTS appointments_anon_deny ON public.appointments;
DROP POLICY IF EXISTS appointments_authenticated_deny ON public.appointments;

CREATE POLICY appointments_anon_deny
ON public.appointments FOR ALL TO anon
USING (false) WITH CHECK (false);

CREATE POLICY appointments_authenticated_deny
ON public.appointments FOR ALL TO authenticated
USING (false) WITH CHECK (false);

-- ========== public.referral_discount_redemptions ==========
DROP POLICY IF EXISTS referral_redemptions_anon_deny ON public.referral_discount_redemptions;
DROP POLICY IF EXISTS referral_redemptions_authenticated_deny ON public.referral_discount_redemptions;

CREATE POLICY referral_redemptions_anon_deny
ON public.referral_discount_redemptions FOR ALL TO anon
USING (false) WITH CHECK (false);

CREATE POLICY referral_redemptions_authenticated_deny
ON public.referral_discount_redemptions FOR ALL TO authenticated
USING (false) WITH CHECK (false);
