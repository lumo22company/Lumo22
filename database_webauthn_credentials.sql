-- WebAuthn / passkey credentials for customer login (future-proof sign-in).
-- Run in Supabase SQL Editor after `customers` exists.

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL,
    public_key TEXT NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0,
    transports JSONB,
    friendly_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT webauthn_credentials_credential_id_unique UNIQUE (credential_id)
);

CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_customer_id ON webauthn_credentials(customer_id);

COMMENT ON TABLE webauthn_credentials IS 'Passkey (WebAuthn) credentials; public keys only, no secrets.';
