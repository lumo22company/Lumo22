# Still no email after checkout — do this once

After **one** test payment, check these two places and note what you see.

---

## A. Stripe: did the webhook get a 200?

1. **Stripe** → **Developers** → **Webhooks** → click your endpoint (Railway URL).
2. Open **Recent events**.
3. Find **checkout.session.completed** for your test payment (match the time).
4. Click it. Look at **Response** (or **Response code**).

**Tell me the code:** 200, 400, 500, or "no such event".

---

## B. Railway: what do the logs say?

1. **Railway** → your service → **Deployments** → latest → **View logs**.
2. Do **one more test payment** (same product, test card).
3. In the logs, search for **Stripe webhook** (or scroll to the time of the payment).

**Tell me exactly what you see**, e.g.:

- `[Stripe webhook] event type=checkout.session.completed`
- `[Stripe webhook] checkout.session.completed amount_total=9700 ... _is_captions_payment=True` (or False)
- `[Stripe webhook] Sending intake email to your@email.com`
- `[SendGrid] Email sent OK` or `[SendGrid] Error sending email` or `intake-link email FAILED`

Or: "No lines containing Stripe webhook."

---

## Important

The intake email is sent to the **email you enter at Stripe Checkout**, not necessarily hello@lumo22.com. So check the inbox (and spam) of **the address you used when paying**.

---

Once you have (A) response code and (B) the log lines (or "no Stripe webhook lines"), paste them here and we can fix the exact cause.
