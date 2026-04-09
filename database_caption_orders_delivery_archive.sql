-- Past subscription packs: each renewal archives the previous PDFs/md before overwriting the row.
-- Run in Supabase SQL Editor.

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS delivery_archive JSONB NOT NULL DEFAULT '[]';

COMMENT ON COLUMN caption_orders.delivery_archive IS
  'Subscription only: array of {delivered_at, captions_md, captions_pdf_base64?, stories_pdf_base64?, include_stories?} for each prior monthly pack.';
