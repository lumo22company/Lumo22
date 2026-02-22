# Captions Pre-Pack Reminder & Subscription Renewal Setup

## 1. Database migration

Run `database_caption_reminder.sql` in Supabase SQL Editor:

```sql
-- Adds reminder_sent_period_end and reminder_opt_out to caption_orders
```

## 2. Environment variables ✓

`CRON_SECRET` is in `.env` and has been added to Railway. For steps 3 & 4, see **CAPTIONS_REMINDER_DO_NOW.md**.

## 3. Stripe webhook

In Stripe Dashboard → Developers → Webhooks → Your endpoint, ensure these events are selected:

- `checkout.session.completed` (already used)
- **`invoice.paid`** (for subscription renewal → auto-generate and deliver new pack)

## 4. Railway cron

Create a cron job to call the reminder endpoint daily (e.g. 9am UTC):

- **URL**: `https://your-app.up.railway.app/api/captions-send-reminders?secret=YOUR_CRON_SECRET`
- **Schedule**: `0 9 * * *` (9am UTC daily)

Or use Railway's cron feature with a GET request.

## 5. Flow summary

| Event | Action |
|-------|--------|
| First payment (checkout) | Create order, send intake email |
| Intake submitted | Generate captions, email PDF |
| 5 days before renewal | Send reminder email with intake link (customers can update) |
| Renewal (invoice.paid) | Regenerate from intake, email new pack |

Reminders are ON by default. Set `reminder_opt_out = true` on an order to disable for that customer.
