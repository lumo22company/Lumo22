# Run this in Supabase (fixes missing column for test script & create_order)

The app expects `caption_orders` to have `upgraded_from_token` (and related columns). If they’re missing, run the following in Supabase.

## Steps

1. Open **[Supabase](https://supabase.com/dashboard)** → your project.
2. Go to **SQL Editor** → **New query**.
3. Paste the SQL below and click **Run**.

```sql
-- Add columns for one-off → subscription upgrade scheduling.
ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
COMMENT ON COLUMN caption_orders.delivered_at IS 'When the pack was delivered. Set by set_delivered. Used for upgrade scheduling.';

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS upgraded_from_token TEXT;
COMMENT ON COLUMN caption_orders.upgraded_from_token IS 'For subscription orders: token of the one-off order this was upgraded from (copy_from). First pack delivered 30 days after one-off.';

ALTER TABLE caption_orders ADD COLUMN IF NOT EXISTS scheduled_delivery_at TIMESTAMPTZ;
COMMENT ON COLUMN caption_orders.scheduled_delivery_at IS 'When to deliver first pack for upgrade-from-one-off. Set on intake submit; cron triggers delivery when due.';
```

4. You should see “Success. No rows returned.” (or similar). Then:
   - The test script `python3 send_test_intake_email.py your@email.com` should work.
   - Order creation (webhook / API) will no longer fail on the missing column.

**Note:** If you use the **pooler** connection string in `DATABASE_URL`, the migration script may still fail with auth. Running this SQL in the SQL Editor uses your Supabase login and doesn’t need `DATABASE_URL`.
