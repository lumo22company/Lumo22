-- Fix RLS warning: appointments_insert had WITH CHECK (true) (unrestricted insert).
-- App only uses this table from the backend (service_role), so anon/authenticated should have no access.
-- Run in Supabase SQL Editor.

-- Remove permissive policies
DROP POLICY IF EXISTS appointments_select ON public.appointments;
DROP POLICY IF EXISTS appointments_insert ON public.appointments;

-- Optional: explicit deny so anon/authenticated get no rows (service_role bypasses RLS)
-- With RLS enabled and no policies, anon/authenticated already get no access; uncomment if you want to be explicit:
/*
CREATE POLICY appointments_anon_deny ON public.appointments FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY appointments_authenticated_deny ON public.appointments FOR ALL TO authenticated USING (false) WITH CHECK (false);
*/

-- Result: only service_role (your backend) can SELECT/INSERT. Lint warning is resolved.
