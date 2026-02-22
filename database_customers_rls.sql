-- RLS for public.customers (fixes "RLS Disabled in Public" lint)
-- Run in Supabase SQL Editor. Safe when backend uses service_role (RLS is bypassed for service_role).

-- Enable RLS. With no permissive policies for anon/authenticated, they get no access.
-- Your app uses SUPABASE_KEY (service_role recommended); service_role bypasses RLS, so nothing breaks.
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;

-- Optional: explicit deny policies (makes intent clear; default with no policies is already deny).
-- Uncomment if you want to be explicit:
/*
CREATE POLICY "customers_anon_deny" ON public.customers FOR ALL TO anon USING (false) WITH CHECK (false);
CREATE POLICY "customers_authenticated_deny" ON public.customers FOR ALL TO authenticated USING (false) WITH CHECK (false);
*/

-- If you later use Supabase Auth and want users to access only their own row, add a policy like:
-- CREATE POLICY "customers_own_row" ON public.customers FOR ALL TO authenticated
--   USING (auth.jwt() ->> 'email' = email);
