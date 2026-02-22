-- Allow the app (Railway) to insert and update caption_orders when using the anon key.
-- Run this in Supabase SQL Editor if your webhook gets 500 and logs show Supabase/RLS errors.

-- Enable RLS (if not already)
ALTER TABLE caption_orders ENABLE ROW LEVEL SECURITY;

-- Allow inserts (e.g. Stripe webhook creating an order)
CREATE POLICY "Allow caption_orders insert"
ON caption_orders
FOR INSERT
TO anon, authenticated, service_role
WITH CHECK (true);

-- Allow select (e.g. get order by stripe_session_id or token for intake link)
CREATE POLICY "Allow caption_orders select"
ON caption_orders
FOR SELECT
TO anon, authenticated, service_role
USING (true);

-- Allow update (e.g. saving intake, setting status to delivered)
CREATE POLICY "Allow caption_orders update"
ON caption_orders
FOR UPDATE
TO anon, authenticated, service_role
USING (true)
WITH CHECK (true);
