# Digital Front Desk — Auto-reply on/off & client-only replies

## What’s included

1. **On/off switch**  
   Customers can turn auto-reply off when they want to handle emails manually, and turn it back on anytime.

2. **Only reply to customer/client emails**  
   You can set domains that should **never** get an auto-reply (e.g. your own company). Only senders from other domains (real clients) get a reply.

## Run the migration

Add the new columns to `front_desk_setups`:

**Option A — Supabase SQL Editor**

1. Supabase Dashboard → **SQL Editor** → New query.
2. Paste the contents of `database_front_desk_auto_reply.sql`.
3. Run.

**Option B — Script (needs DATABASE_URL)**

```bash
# With DATABASE_URL in .env, run the SQL in database_front_desk_auto_reply.sql
# (You can use the same pattern as run_tight_scheduling_migration.py if you add a runner script.)
```

After the migration:

- `auto_reply_enabled` (boolean, default true) — when false, inbound emails are not auto-replied.
- `skip_reply_domains` (text, optional) — comma-separated domains; we never reply to senders whose email domain is in this list.

## How customers use it

### Setup form

- **Domains to never auto-reply to** — e.g. `mybusiness.com, mycompany.co.uk`. Senders from these domains never get an auto-reply (so only external/client emails do).
- **Auto-reply to new enquiries** — checkbox, on by default. They can turn it off later via the link in the confirmation email.

### After setup

The confirmation email includes two links:

- **Pause auto-reply** — open this when they want to handle emails manually. No new auto-replies are sent until they turn it back on.
- **Resume auto-reply** — open this to turn auto-reply back on.

Links use the secret `done_token`, so only the recipient can use them.

## API (for integrations)

- `GET /api/front-desk-setup/pause-auto-reply?token=<done_token>` — turn auto-reply off.
- `GET /api/front-desk-setup/resume-auto-reply?token=<done_token>` — turn auto-reply on.

Both return a simple HTML page confirming the change.

## Behaviour summary

| Scenario | Result |
|----------|--------|
| `auto_reply_enabled` is false | No auto-reply; we return 200 so SendGrid doesn’t retry. |
| Sender’s domain is in `skip_reply_domains` | No auto-reply (only external/client emails get a reply). |
| Otherwise | Reply is generated and sent as before. |

Existing setups without these columns behave as before (auto-reply on, no domain filter) until you run the migration.
