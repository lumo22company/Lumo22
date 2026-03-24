-- Store Captions PDF at delivery so account/history can serve the original artifact
-- even if PDF regeneration later fails.

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS captions_pdf_base64 TEXT;

COMMENT ON COLUMN caption_orders.captions_pdf_base64 IS
'Base64-encoded Captions PDF saved at delivery time; used for resilient download and resend flows.';
