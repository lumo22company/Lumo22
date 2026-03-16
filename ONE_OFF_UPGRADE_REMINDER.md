# One-off upgrade reminder

We send a **single email** to one-off customers a few days before their "day 30" (when their pack period ends), offering to upgrade to a subscription.

## When we send

- **Default:** 5 days before day 30 → email is sent when **25 days** have passed since `delivered_at`.
- **Optional:** Set `ONE_OFF_UPGRADE_REMINDER_DAYS_BEFORE=3` in env to send 3 days before (i.e. **27 days** after delivery).

The same cron that runs subscription reminders (`/api/captions-send-reminders`) also runs one-off upgrade reminders once per day. Each eligible order receives the email at most once (tracked by `upgrade_reminder_sent_at`).

## Flow for one-off users upgrading to subscription

1. They receive the upgrade email and click the link → they are sent to **subscription checkout** (URL includes `copy_from` so their form answers are prefilled).
2. **Login required:** All subscription checkouts (including upgrade) require an account. If they're not logged in, they're redirected to **login** (or signup) with `next=` back to the checkout URL so they return there after signing in.
3. They log in or create an account (same email as their one-off order), then complete the subscription payment on Stripe.
4. After payment they receive the **subscription welcome** email: "You're subscribed. Log in to access your form (prefilled from your one-off pack)."

So: **all subscribers (new and upgrade) must have an account before payment.** The upgrade reminder email tells them they'll need to log in or create an account first.

## Database migration

Run the SQL in **Supabase SQL Editor** so the app can record reminder sends and opt-outs:

```sql
-- See database_caption_orders_upgrade_reminder.sql
ALTER TABLE caption_orders
  ADD COLUMN IF NOT EXISTS upgrade_reminder_sent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS upgrade_reminder_opt_out BOOLEAN DEFAULT false;
```

## Opt-out

Each reminder email includes an **Unsubscribe from upgrade reminders** link. It goes to:

`/api/captions-upgrade-reminder-unsubscribe?t=TOKEN`

That sets `upgrade_reminder_opt_out = true` for that order and shows a short confirmation page.

## Legal

- **Terms:** We state that we may send one-off customers a single email before day 30 offering to upgrade, and that they can unsubscribe via the link in the email.
- **Privacy:** We state that we send this upgrade-reminder email and that they can unsubscribe via the link in the email.

See `_terms_content.html` and `_privacy_content.html`.
