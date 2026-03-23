# Why multiple subscriptions / duplicate packs can appear

## What happened (typical case)

1. **Each time you complete Stripe Checkout for the monthly Captions plan**, Stripe creates a **new** subscription and our system creates a **new** order row (new intake link `?t=...`).
2. **Email links** always point at **one specific** order token. If you subscribed several times, you may have **several different links** in old emails — opening each and submitting the form can trigger **one delivery per order**.
3. **Account → Complete / Edit form** works on **one** order at a time (the subscription you pick). Filling the form from the account **does not remove** the other subscription rows — they stay in the database and Stripe until you cancel them.
4. **Showing the “same” business name** on multiple rows is expected after we **sync display** from your one-off upgrade: the UI can show the same name on each subscription line even though they are **separate** Stripe subscriptions.

## What to do now

1. **Stripe billing**: Go to **Account → Manage billing** (or Manage subscription) and **cancel extra subscriptions** you don’t want, so you’re only charged once per month.
2. **Use a single order**: Prefer **one** intake link — either the one from the **latest** subscription email or **Account → Edit form** for the subscription you want to keep.
3. **Going forward**: The app now **blocks** starting a new subscription checkout if you already have an **active** Captions subscription on that account (so repeat checkouts don’t create more rows).

## Support

If you’re unsure which subscription to keep, email **hello@lumo22.com** with your account email and we can help identify duplicates in Stripe.
