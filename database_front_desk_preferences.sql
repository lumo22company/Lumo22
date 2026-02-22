-- Adds enquiry_types, opening_hours, reply_same_day, reply_24h, tone, good_lead_rules to front_desk_setups.
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).
-- Used by chat setup (step 2) and future DFD step 2; passed into reply generation for tailored responses.

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS enquiry_types JSONB;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS opening_hours TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS reply_same_day BOOLEAN DEFAULT false;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS reply_24h BOOLEAN DEFAULT false;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS tone TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS good_lead_rules TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

COMMENT ON COLUMN front_desk_setups.enquiry_types IS 'Array of enquiry types (pricing, booking_appointments, etc.) for chat/reply context';
COMMENT ON COLUMN front_desk_setups.opening_hours IS 'e.g. Mon–Fri 9am–6pm — sets expectations in replies';
COMMENT ON COLUMN front_desk_setups.reply_same_day IS 'We usually reply same day';
COMMENT ON COLUMN front_desk_setups.reply_24h IS 'We usually reply within 24 hours';
COMMENT ON COLUMN front_desk_setups.tone IS 'friendly_relaxed, professional_smart, warm_reassuring, short_direct';
COMMENT ON COLUMN front_desk_setups.good_lead_rules IS 'When to encourage booking (e.g. when they mention service, timeframe, budget)';
