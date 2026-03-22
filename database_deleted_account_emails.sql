-- Blocklist of emails from deleted accounts. Used to ensure reminder emails
-- (and any future mailings) are never sent to people who have deleted their account.
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS deleted_account_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deleted_account_emails_email ON deleted_account_emails(email);
COMMENT ON TABLE deleted_account_emails IS 'Emails of users who deleted their account. Never send reminder or marketing emails to these addresses.';

-- RLS + policies (backend uses anon key from CaptionOrderService)
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

CREATE POLICY "deleted_account_emails_delete"
ON public.deleted_account_emails FOR DELETE
TO anon, authenticated, service_role
USING (email IS NOT NULL AND trim(email) <> '');
