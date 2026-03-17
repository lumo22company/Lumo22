# Upgrade flows & emails

## Customer never sees "trial"

- The word **trial** is only used in backend/Stripe (e.g. `subscription_data.trial_end`). It does **not** appear in any template or user-facing copy.

---

## Scenarios

### 1. Upgrader, charge on delivery (no “Get your first pack now”)

- **Checkout:** Subscription created with `trial_end` = 30 days after one-off `delivered_at`. No charge at checkout.
- **Copy on page:** “You won’t be charged today. You’ll be charged £79/month when your first subscription pack is ready (on [date]).”
- **Emails they receive:**
  - **One email only:** “You’re set up — 30 Days Captions subscription” (upgrade confirmation).
  - Says: you’re set up, you won’t be charged today, we’ll charge when your first pack is ready (on [date]), form is prefilled, link to form.
  - **No** “Thanks for your order / We’ve received your payment” receipt (because nothing was charged).
- **When trial ends:** Stripe charges; `invoice.paid` runs; we copy intake from one-off if needed, then generate and send the pack.

### 2. Upgrader, “Get your first pack now” checked

- **Checkout:** Normal subscription checkout (no trial). Charged at checkout.
- **Copy on page:** “You’ll be charged today and we’ll send your first pack right away. Your next billing date will be 30 days from today.”
- **Emails they receive:**
  - **Receipt:** “Thanks for your order — 30 Days of Social Media Captions” (amount paid, order details).
  - **Welcome:** “You’re subscribed — 30 Days Captions” (form prefilled, link to form).
- **Webhook:** After `_handle_captions_payment`, we copy intake from one-off and trigger delivery immediately.

### 3. New subscriber (not from one-off)

- **Checkout:** Normal subscription, charged at checkout.
- **Emails:** Receipt + intake link email (complete your form).

### 4. First charge after trial (upgrader, charge on delivery)

- **Trigger:** `invoice.paid` with `billing_reason=subscription_cycle` when trial ends.
- **Behaviour:** Find order by subscription; if no intake and `upgraded_from_token` set, copy intake from one-off, then run generation and delivery. PDF only created after successful charge.

---

## Summary: confirmation of upgrade

- **Charge on delivery (trial):** One email = “You’re set up — 30 Days Captions subscription” with charge date and form link. That is the **confirmation of upgrade**; no separate “payment received” email.
- **Get pack now (charged today):** Receipt email + “You’re subscribed — 30 Days Captions” welcome. Receipt is the payment confirmation; welcome is the subscription/upgrade confirmation.
