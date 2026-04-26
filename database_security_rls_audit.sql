-- Supabase RLS audit for Lumo 22 (read-only).
-- Run in Supabase SQL Editor. It does NOT change data/policies.
--
-- This file returns ONE result table (multiple sections) so Supabase is easier to read
-- than a multi-statement script where only the last result appears.

WITH
expected(table_name) AS (
  VALUES
    ('caption_orders'),
    ('customers'),
    ('webauthn_credentials'),
    ('deleted_account_emails'),
    ('referral_discount_redemptions')
),
t AS (
  SELECT n.nspname AS schema_name, c.relname AS table_name, c.relrowsecurity AS rls_enabled
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind = 'r'
),
rls_check AS (
  SELECT
    1 AS sort_key,
    'RLS enabled check' AS section,
    e.table_name AS item,
    CASE
      WHEN t.table_name IS NULL THEN 'FAIL: table missing'
      WHEN t.rls_enabled THEN 'PASS'
      ELSE 'FAIL: RLS disabled'
    END AS result,
    COALESCE(t.rls_enabled::text, 'false') AS detail
  FROM expected e
  LEFT JOIN t ON t.table_name = e.table_name
),
policy_rows AS (
  SELECT
    2 AS sort_key,
    'Policy inventory' AS section,
    tablename || ' / ' || policyname AS item,
    cmd AS result,
    'roles=' || COALESCE(roles::text, '') || ' | USING=' || COALESCE(qual, '') || ' | WITH check=' || COALESCE(with_check::text, '') AS detail
  FROM pg_policies
  WHERE schemaname = 'public'
    AND tablename IN (
      'caption_orders','customers','webauthn_credentials','deleted_account_emails','referral_discount_redemptions'
    )
),
broad_select AS (
  SELECT
    3 AS sort_key,
    'Broad SELECT policy' AS section,
    tablename || ' / ' || policyname AS item,
    CASE
      WHEN cmd = 'SELECT'
           AND (roles::text ILIKE '%anon%' OR roles::text ILIKE '%authenticated%')
           AND (qual IS NULL OR btrim(qual) IN ('true', '(true)'))
        THEN 'WARN: broad row visibility'
      ELSE 'OK'
    END AS result,
    'roles=' || COALESCE(roles::text, '') || ' | USING=' || COALESCE(qual, '') AS detail
  FROM pg_policies
  WHERE schemaname = 'public'
    AND tablename IN ('caption_orders','customers','deleted_account_emails')
    AND cmd = 'SELECT'
),
next_action AS (
  SELECT
    4 AS sort_key,
    'Next action' AS section,
    'caption_orders anon/auth SELECT exposure' AS item,
    CASE
      WHEN EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='caption_orders' AND cmd='SELECT'
          AND (roles::text ILIKE '%anon%' OR roles::text ILIKE '%authenticated%')
          AND (qual IS NULL OR btrim(qual) IN ('true','(true)'))
      )
        THEN 'If app uses service_role on backend, tighten caption_orders SELECT for anon/authenticated (or explicit deny policies).'
      ELSE 'caption_orders SELECT is not broadly exposed to anon/authenticated.'
    END AS result,
    '' AS detail
  UNION ALL
  SELECT
    4 AS sort_key,
    'Next action' AS section,
    'deleted_account_emails anon/auth SELECT exposure' AS item,
    CASE
      WHEN EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname='public' AND tablename='deleted_account_emails' AND cmd='SELECT'
          AND (roles::text ILIKE '%anon%' OR roles::text ILIKE '%authenticated%')
          AND (qual IS NULL OR btrim(qual) IN ('true','(true)'))
      )
        THEN 'If app uses service_role on backend, tighten deleted_account_emails SELECT for anon/authenticated.'
      ELSE 'deleted_account_emails SELECT is not broadly exposed to anon/authenticated.'
    END AS result,
    '' AS detail
)
SELECT section, item, result, detail
FROM (
  SELECT * FROM rls_check
  UNION ALL
  SELECT * FROM policy_rows
  UNION ALL
  SELECT * FROM broad_select
  UNION ALL
  SELECT * FROM next_action
) u
ORDER BY sort_key, section, item;
