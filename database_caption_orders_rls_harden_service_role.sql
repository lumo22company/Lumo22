-- Harden caption_orders RLS: deny anon/authenticated access explicitly.
--
-- IMPORTANT PREREQ:
-- Your backend must use SUPABASE_SERVICE_ROLE_KEY for caption_orders operations.
-- service_role bypasses RLS, so app behavior remains intact.
--
-- Run in Supabase SQL Editor.

ALTER TABLE public.caption_orders ENABLE ROW LEVEL SECURITY;

-- Remove previous broad policies (old names and newer names).
DROP POLICY IF EXISTS "Allow caption_orders insert" ON public.caption_orders;
DROP POLICY IF EXISTS "Allow caption_orders select" ON public.caption_orders;
DROP POLICY IF EXISTS "Allow caption_orders update" ON public.caption_orders;
DROP POLICY IF EXISTS "caption_orders_insert" ON public.caption_orders;
DROP POLICY IF EXISTS "caption_orders_select" ON public.caption_orders;
DROP POLICY IF EXISTS "caption_orders_update" ON public.caption_orders;
DROP POLICY IF EXISTS "caption_orders_anon_authenticated_deny_all" ON public.caption_orders;

-- Explicit deny for client-facing roles.
CREATE POLICY "caption_orders_anon_authenticated_deny_all"
ON public.caption_orders
FOR ALL
TO anon, authenticated
USING (false)
WITH CHECK (false);

-- Optional verification output
SELECT
  schemaname, tablename, policyname, cmd, roles, qual, with_check
FROM pg_policies
WHERE schemaname='public' AND tablename='caption_orders'
ORDER BY policyname;
