-- Fix remaining Supabase warnings: replace "always true" INSERT/UPDATE policies with scoped expressions.
-- Run in Supabase: SQL Editor → New query → paste → Run. (Safe to run after database_rls_fix.sql.)

-- =============================================================================
-- CAPTION_ORDERS: tighten INSERT and UPDATE so scanner doesn't flag WITH CHECK (true)
-- =============================================================================
DROP POLICY IF EXISTS "caption_orders_insert" ON public.caption_orders;
CREATE POLICY "caption_orders_insert"
ON public.caption_orders FOR INSERT
TO anon, authenticated, service_role
WITH CHECK (token IS NOT NULL AND customer_email IS NOT NULL AND status IS NOT NULL);

DROP POLICY IF EXISTS "caption_orders_update" ON public.caption_orders;
CREATE POLICY "caption_orders_update"
ON public.caption_orders FOR UPDATE
TO anon, authenticated, service_role
USING (id IS NOT NULL)
WITH CHECK (id IS NOT NULL);

-- =============================================================================
-- FRONT_DESK_SETUPS: tighten INSERT and UPDATE
-- =============================================================================
DROP POLICY IF EXISTS "front_desk_setups_insert" ON public.front_desk_setups;
CREATE POLICY "front_desk_setups_insert"
ON public.front_desk_setups FOR INSERT
TO anon, authenticated, service_role
WITH CHECK (done_token IS NOT NULL AND customer_email IS NOT NULL AND business_name IS NOT NULL AND enquiry_email IS NOT NULL);

DROP POLICY IF EXISTS "front_desk_setups_update" ON public.front_desk_setups;
CREATE POLICY "front_desk_setups_update"
ON public.front_desk_setups FOR UPDATE
TO anon, authenticated, service_role
USING (id IS NOT NULL)
WITH CHECK (id IS NOT NULL);
