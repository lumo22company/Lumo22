-- Store Stories PDF at delivery so account history serves the same artifact as captions.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS stories_pdf_base64 TEXT;
COMMENT ON COLUMN caption_orders.stories_pdf_base64 IS 'Base64-encoded Stories PDF, set at delivery when include_stories is true. Served from account history instead of regenerating.';
