-- Lumo 22 customer accounts: one account per email for DFD, Chat, Captions
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

COMMENT ON TABLE customers IS 'Lumo 22 customer accounts: DFD, Chat, Captions. One per email.';
