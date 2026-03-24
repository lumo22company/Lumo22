-- Enable RLS on webauthn_credentials and deleted_account_emails (Supabase linter / PostgREST exposure).
-- Run in Supabase: Dashboard → SQL Editor → paste → Run.
--
-- webauthn_credentials: RLS ON, no policies. Only the service_role key bypasses RLS — matches
-- WebAuthnCredentialService (SUPABASE_SERVICE_ROLE_KEY preferred). Anon cannot read passkeys via API.
--
-- deleted_account_emails: RLS ON + policies for anon/authenticated/service_role because
-- CaptionOrderService uses SUPABASE_KEY (anon) for insert/select/delete.

-- =============================================================================
-- WEBAUTHN_CREDENTIALS
-- =============================================================================
ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY;

-- Explicit deny for anon/authenticated (service_role bypasses RLS). Satisfies linter "no policies" warning.
DROP POLICY IF EXISTS "webauthn_credentials_deny_anon_auth" ON public.webauthn_credentials;
CREATE POLICY "webauthn_credentials_deny_anon_auth"
ON public.webauthn_credentials FOR ALL
TO anon, authenticated
USING (false)
WITH CHECK (false);

-- =============================================================================
-- DELETED_ACCOUNT_EMAILS
-- =============================================================================
ALTER TABLE public.deleted_account_emails ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deleted_account_emails_insert" ON public.deleted_account_emails;
DROP POLICY IF EXISTS "deleted_account_emails_select" ON public.deleted_account_emails;
DROP POLICY IF EXISTS "deleted_account_emails_delete" ON public.deleted_account_emails;

CREATE POLICY "deleted_account_emails_insert"
ON public.deleted_account_emails FOR INSERT
TO anon, authenticated, service_role
WITH CHECK (email IS NOT NULL AND trim(email) <> '');

CREATE POLICY "deleted_account_emails_select"
ON public.deleted_account_emails FOR SELECT
TO anon, authenticated, service_role
USING (true);

-- USING: email must exist (column is NOT NULL; avoids linter "always true" warning)
CREATE POLICY "deleted_account_emails_delete"
ON public.deleted_account_emails FOR DELETE
TO anon, authenticated, service_role
USING (email IS NOT NULL AND trim(email) <> '');
