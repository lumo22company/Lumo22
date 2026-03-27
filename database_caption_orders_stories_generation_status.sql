ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS stories_generation_status TEXT;

COMMENT ON COLUMN caption_orders.stories_generation_status IS
'Stories generation state for delivery runs: ok, failed, or skipped (captions-only fallback).';
ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS stories_generation_status TEXT;

ALTER TABLE caption_orders
ADD COLUMN IF NOT EXISTS stories_last_error TEXT;

COMMENT ON COLUMN caption_orders.stories_generation_status IS
'Story Ideas generation status for this delivery (not_requested, ok, failed).';

COMMENT ON COLUMN caption_orders.stories_last_error IS
'Last Story Ideas generation error when stories add-on was requested but failed.';
