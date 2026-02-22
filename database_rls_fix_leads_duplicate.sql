-- Remove duplicate SELECT policy on leads (keep only leads_select).
-- Run in Supabase: SQL Editor → New query → paste → Run.

DROP POLICY IF EXISTS "Allow public reads on leads" ON public.leads;
