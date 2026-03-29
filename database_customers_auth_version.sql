-- Run once in Supabase SQL editor: invalidate all sessions when password changes (sign out everywhere).
ALTER TABLE customers ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;
COMMENT ON COLUMN customers.auth_version IS 'Incremented on password reset; session must match or user is logged out.';
