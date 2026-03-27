ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS email_change_events JSONB NOT NULL DEFAULT '[]';

COMMENT ON COLUMN caption_orders.email_change_events IS
'Audit trail for thank-you Wrong email corrections (timestamp, old/new email, IP, user agent, source).';
