-- Harden deleted_account_emails RLS: deny anon/authenticated access explicitly.
--
-- IMPORTANT PREREQ:
-- Your backend should use SUPABASE_SERVICE_ROLE_KEY for deleted_account_emails operations.
-- service_role bypasses RLS, so app behavior remains intact.
--
-- Run in Supabase SQL Editor.

ALTER TABLE public.deleted_account_emails ENABLE ROW LEVEL SECURITY;

-- Remove older permissive policies.
DROP POLICY IF EXISTS "deleted_account_emails_insert" ON public.deleted_account_emails;
DROP POLICY IF EXISTS "deleted_account_emails_select" ON public.deleted_account_emails;
DROP POLICY IF EXISTS "deleted_account_emails_delete" ON public.deleted_account_emails;
DROP POLICY IF EXISTS "deleted_account_emails_anon_authenticated_deny_all" ON public.deleted_account_emails;

-- Explicit deny for client-facing roles.
CREATE POLICY "deleted_account_emails_anon_authenticated_deny_all"
ON public.deleted_account_emails
FOR ALL
TO anon, authenticated
USING (false)
WITH CHECK (false);

-- Optional verification output
SELECT
  schemaname, tablename, policyname, cmd, roles, qual, with_check
FROM pg_policies
WHERE schemaname='public' AND tablename='deleted_account_emails'
ORDER BY policyname;
