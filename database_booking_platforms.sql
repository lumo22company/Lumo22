-- Add booking platform integration columns to front_desk_setups.
-- Run in Supabase SQL Editor.
-- Enables Calendly, Vagaro, etc. to provide real-time availability.

ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS booking_platform TEXT DEFAULT 'generic';
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS calendly_api_token TEXT;
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS calendly_event_type_uri TEXT;
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS vagaro_access_token TEXT;
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS vagaro_business_id TEXT;
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS vagaro_service_id TEXT;
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS vagaro_region TEXT DEFAULT 'us';

COMMENT ON COLUMN front_desk_setups.booking_platform IS 'calendly, vagaro, or generic (work hours + appointments table)';
COMMENT ON COLUMN front_desk_setups.calendly_api_token IS 'Calendly Personal Access Token for availability API';
COMMENT ON COLUMN front_desk_setups.calendly_event_type_uri IS 'Calendly event type URI, e.g. https://api.calendly.com/event_types/XXX';
