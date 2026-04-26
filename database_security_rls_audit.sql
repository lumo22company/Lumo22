-- Supabase RLS audit for Lumo 22 (read-only).
-- Run in Supabase SQL Editor. It does NOT change data/policies.
-- After running, review rows marked WARN/FAIL.

-- 1) RLS enabled on sensitive tables
WITH expected(table_name) AS (
  VALUES
    ('caption_orders'),
    ('customers'),
    ('webauthn_credentials'),
    ('deleted_account_emails'),
    ('appointments'),
    ('referral_discount_redemptions')
), t AS (
  SELECT n.nspname AS schema_name, c.relname AS table_name, c.relrowsecurity AS rls_enabled
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind = 'r'
)
SELECT
  'RLS enabled check' AS check_name,
  e.table_name,
  COALESCE(t.rls_enabled, false) AS rls_enabled,
  CASE
    WHEN t.table_name IS NULL THEN 'FAIL: table missing'
    WHEN t.rls_enabled THEN 'PASS'
    ELSE 'FAIL: RLS disabled'
  END AS result
FROM expected e
LEFT JOIN t ON t.table_name = e.table_name
ORDER BY e.table_name;

-- 2) Policy inventory for sensitive tables
SELECT
  'Policy inventory' AS check_name,
  schemaname,
  tablename,
  policyname,
  cmd,
  roles,
  qual,
  with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
    'caption_orders','customers','webauthn_credentials','deleted_account_emails','appointments','referral_discount_redemptions'
  )
ORDER BY tablename, policyname;

-- 3) Dangerous broad SELECT access for anon/authenticated on core tables
-- Goal: detect "USING (true)" style policies that expose all rows if anon/auth key is used from client side.
SELECT
  'Broad SELECT policy' AS check_name,
  schemaname,
  tablename,
  policyname,
  roles,
  COALESCE(qual, '') AS using_expr,
  CASE
    WHEN cmd = 'SELECT'
         AND (roles::text ILIKE '%anon%' OR roles::text ILIKE '%authenticated%')
         AND (qual IS NULL OR btrim(qual) IN ('true', '(true)'))
      THEN 'WARN: broad row visibility'
    ELSE 'OK'
  END AS result
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('caption_orders','customers')
  AND cmd = 'SELECT'
ORDER BY tablename, policyname;

-- 4) Recommended next actions (read output only)
SELECT
  'Next action' AS check_name,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname='public' AND tablename='caption_orders' AND cmd='SELECT'
        AND (roles::text ILIKE '%anon%' OR roles::text ILIKE '%authenticated%')
        AND (qual IS NULL OR btrim(qual) IN ('true','(true)'))
    )
      THEN 'If app uses service_role on backend, tighten caption_orders SELECT for anon/authenticated (or explicit deny policies).'
    ELSE 'caption_orders SELECT is not broadly exposed to anon/authenticated.'
  END AS recommendation;
