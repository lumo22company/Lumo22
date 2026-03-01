# Adding Stories: When, Billing, and When Stories Are Generated

## Can a customer add Stories at any time?

**Yes, but only via a new purchase.** There is no “add Stories to my current subscription” flow in the app.

- **From the intake form (editing):** If they tick “Include Story Ideas” but their order doesn’t include Stories, the API returns `upgrade_required` and sends them to `/captions?stories=1`. That starts a **new** Stripe Checkout (one-off or subscription with Stories).
- **Directly:** They can go to the product page with `?stories=1` and complete checkout. Again, that creates a **new** order (and, for subscription, a **new** Stripe subscription).

So “add Stories at any time” means: **start a new checkout that includes Stories**. The app does **not** update an existing subscription to add the Stories price (no Stripe “add another price to this subscription” / proration flow).

---

## How does adding Stories affect billing?

- **One-off:** A new one-off checkout with Stories creates one new order. They pay once (base + Stories one-off price). No recurring billing.
- **Subscription:** A new subscription checkout with Stories creates a **new** Stripe subscription (base + Stories recurring). So if they already have a captions-only subscription and then do “add Stories” via `/captions?stories=1` and choose subscription, they would end up with **two** subscriptions (one captions-only, one captions+Stories) unless they cancel the first. The app does not:
  - Add the Stories price to their existing subscription, or
  - Prorate / align the billing cycle when “adding” Stories.

So today, adding Stories = **new purchase**; for subscriptions that can mean a second subscription unless you direct them to cancel the old one and re-subscribe with Stories.

---

## When are Stories generated?

Stories are generated **only when a pack is delivered**, not on a separate schedule.

- **First-time (one-off or first subscription payment):** When they submit the intake form, the app runs `_run_generation_and_deliver(order_id)`. That generates captions, then if the order has `include_stories` and the intake has `include_stories`, it builds the Stories PDF and attaches it to the delivery email. So Stories are generated **at the same time as the captions** for that pack.
- **Subscription renewal:** On `invoice.paid` (billing_reason `subscription_cycle`), the app finds the order by `stripe_subscription_id` and runs `_run_generation_and_deliver(order_id)` again. That order’s `include_stories` was set when the subscription was created. So each month, if that order has Stories, the renewal run generates both captions and Stories for the new pack and emails them.

So: **Stories are generated per pack, at delivery time** (first intake submit or subscription renewal), not “on demand” or at a different time from captions.

---

## Summary

| Question | Answer |
|----------|--------|
| Can they add Stories at any time? | Yes, by starting a new checkout with Stories (`/captions?stories=1`). Not by upgrading the current subscription in place. |
| Billing impact | New purchase = new order; if subscription, that’s a new subscription (risk of two subscriptions if they already had one). No proration or “add to existing sub” yet. |
| When are Stories generated? | Only when that pack is delivered: first intake submit or subscription renewal. Same run as captions for that pack. |

---

## Possible improvement: “Add Stories to existing subscription”

To support “add Stories at any time” without a second subscription:

1. **Stripe:** Use [Subscription update](https://stripe.com/docs/api/subscriptions/update) to add the Stories subscription price to the existing subscription. Stripe can prorate.
2. **App:** Expose an “Add Story Ideas to my plan” (or similar) that triggers that update, then update the existing order’s `include_stories` (and optionally backfill Stories for the current month if you want to deliver a Stories pack immediately).

That would keep one subscription and one billing cycle, with Stories included from the next invoice (or prorated).
