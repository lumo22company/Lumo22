-- Launch cleanup (safe) for Supabase production go-live.
-- Purpose: remove TEST/DEMO data while preserving schema, policies, migrations.
--
-- HOW TO USE
-- 1) Open Supabase SQL Editor on the target project.
-- 2) Run section A (preview) first and review counts.
-- 3) In section B, change v_confirm from 'NO' to 'YES_DELETE_TEST_DATA'
-- 4) Run section B only when you're sure.
--
-- NOTES
-- - This script targets obvious test/demo emails and Stripe test ids.
-- - It does NOT drop tables, policies, or columns.
-- - It keeps deleted_account_emails by default (compliance / suppression history).

-- =========================================================
-- A) PREVIEW (read-only): what would be removed?
-- =========================================================
WITH test_emails AS (
  SELECT lower(trim(email)) AS email FROM public.customers
  WHERE lower(trim(email)) ~ '(^test[+._-]|[+._-]test[0-9]*@|example\.com$|mailinator\.com$|tempmail|demo|sample|qa|staging|local|fake)'
  UNION
  SELECT lower(trim(customer_email)) AS email FROM public.caption_orders
  WHERE lower(trim(customer_email)) ~ '(^test[+._-]|[+._-]test[0-9]*@|example\.com$|mailinator\.com$|tempmail|demo|sample|qa|staging|local|fake)'
)
SELECT 'customers (matched by email pattern)' AS item, count(*) AS rows
FROM public.customers c
WHERE lower(trim(c.email)) IN (SELECT email FROM test_emails)
UNION ALL
SELECT 'caption_orders (matched by email pattern)', count(*)
FROM public.caption_orders o
WHERE lower(trim(o.customer_email)) IN (SELECT email FROM test_emails)
UNION ALL
SELECT 'caption_orders (stripe_session_id starts with cs_test_)', count(*)
FROM public.caption_orders o
WHERE coalesce(o.stripe_session_id, '') LIKE 'cs_test_%'
UNION ALL
SELECT 'referral_discount_redemptions (for matched customers)', count(*)
FROM public.referral_discount_redemptions r
WHERE r.customer_id IN (
  SELECT c.id FROM public.customers c
  WHERE lower(trim(c.email)) IN (SELECT email FROM test_emails)
);

-- Optional spot-check list:
-- SELECT id, email, created_at FROM public.customers WHERE lower(email) ~ 'test|demo|sample|qa|staging|example\.com' ORDER BY created_at DESC;
-- SELECT id, customer_email, stripe_session_id, created_at FROM public.caption_orders WHERE lower(customer_email) ~ 'test|demo|sample|qa|staging|example\.com' ORDER BY created_at DESC;


-- =========================================================
-- B) EXECUTE CLEANUP (requires explicit confirmation)
-- =========================================================
DO $$
DECLARE
  v_confirm text := 'NO'; -- CHANGE TO: YES_DELETE_TEST_DATA
  v_del_customers int := 0;
  v_del_orders int := 0;
  v_del_referrals int := 0;
  v_del_auth_users int := 0;
BEGIN
  IF v_confirm <> 'YES_DELETE_TEST_DATA' THEN
    RAISE EXCEPTION 'Safety stop: set v_confirm to YES_DELETE_TEST_DATA before running cleanup.';
  END IF;

  -- Build target email set in a temp table for consistent deletes.
  CREATE TEMP TABLE _launch_cleanup_test_emails(email text primary key) ON COMMIT DROP;

  INSERT INTO _launch_cleanup_test_emails(email)
  SELECT DISTINCT lower(trim(email)) FROM public.customers
  WHERE lower(trim(email)) ~ '(^test[+._-]|[+._-]test[0-9]*@|example\.com$|mailinator\.com$|tempmail|demo|sample|qa|staging|local|fake)';

  INSERT INTO _launch_cleanup_test_emails(email)
  SELECT DISTINCT lower(trim(customer_email)) FROM public.caption_orders
  WHERE lower(trim(customer_email)) ~ '(^test[+._-]|[+._-]test[0-9]*@|example\.com$|mailinator\.com$|tempmail|demo|sample|qa|staging|local|fake)'
  ON CONFLICT DO NOTHING;

  -- Expand email set from explicit Stripe test session ids.
  INSERT INTO _launch_cleanup_test_emails(email)
  SELECT DISTINCT lower(trim(customer_email))
  FROM public.caption_orders
  WHERE coalesce(stripe_session_id, '') LIKE 'cs_test_%'
    AND customer_email IS NOT NULL
    AND trim(customer_email) <> ''
  ON CONFLICT DO NOTHING;

  -- 1) Delete referral redemptions linked to test customers first (FK-safe).
  DELETE FROM public.referral_discount_redemptions r
  USING public.customers c, _launch_cleanup_test_emails t
  WHERE r.customer_id = c.id
    AND lower(trim(c.email)) = t.email;
  GET DIAGNOSTICS v_del_referrals = ROW_COUNT;

  -- 2) Delete caption orders for test emails or explicit Stripe test sessions.
  DELETE FROM public.caption_orders o
  USING _launch_cleanup_test_emails t
  WHERE lower(trim(o.customer_email)) = t.email
     OR coalesce(o.stripe_session_id, '') LIKE 'cs_test_%';
  GET DIAGNOSTICS v_del_orders = ROW_COUNT;

  -- 3) Delete customers for test emails.
  DELETE FROM public.customers c
  USING _launch_cleanup_test_emails t
  WHERE lower(trim(c.email)) = t.email;
  GET DIAGNOSTICS v_del_customers = ROW_COUNT;

  -- 4) Best-effort delete matching Supabase Auth users (same emails).
  -- SQL Editor usually has rights on auth.users. If not, this block warns and continues.
  BEGIN
    DELETE FROM auth.users u
    USING _launch_cleanup_test_emails t
    WHERE lower(trim(u.email)) = t.email;
    GET DIAGNOSTICS v_del_auth_users = ROW_COUNT;
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not delete from auth.users (permission/schema restriction): %', SQLERRM;
  END;

  RAISE NOTICE 'Launch cleanup complete. Deleted: customers=% caption_orders=% referral_redemptions=% auth.users=%',
    v_del_customers, v_del_orders, v_del_referrals, v_del_auth_users;
END $$;

