-- Enable RLS on referral_discount_redemptions (Supabase recommends RLS on all public tables).
-- The app only accesses this table from the backend using the service_role key, which bypasses RLS.
-- With RLS enabled and no policies, anon/authenticated get no access; service_role still has full access.
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).

ALTER TABLE public.referral_discount_redemptions ENABLE ROW LEVEL SECURITY;
