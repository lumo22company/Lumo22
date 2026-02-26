# Refer-a-friend codes and Stripe

## Current state (Option B implemented)

**Referral codes in the app**
- Customers get a unique referral code and link (e.g. `/signup?ref=ABC123` or `/captions?ref=ABC123`) from **Account → Refer a friend**.
- When someone signs up with that link, we store `referred_by_customer_id` so we know who referred whom.
- **Discount at checkout:** If you set `STRIPE_REFERRAL_COUPON_ID` (Stripe Coupon ID, e.g. 10% off once), the app automatically applies that coupon when:
  - The customer has `ref=CODE` in the URL and the code matches an existing referrer, or
  - The customer is logged in and has `referred_by_customer_id` set (they signed up via a referral link).
- The discount is applied to both one-off and subscription captions checkout.

---

## What discount to use

Common choices for “friend” discounts:

| Option | Example | Pros / cons |
|--------|--------|-------------|
| **10% off first purchase** | £97 → £87.30 one-off; £79 → £71.10 first month | Simple, familiar, scales with plan. |
| **Fixed amount off** | £10 off first order | Easy to communicate; same for one-off and sub. |
| **First month half price (subscription)** | £79 → £39.50 first month | Strong incentive for subscription. |
| **One free month after first paid (subscription)** | Pay first month, second month free | More generous; needs Stripe subscription trial or credit. |

A simple choice that works for both one-off and subscription: **10% off the first payment** (one-off or first month). So:
- One-off £97 → **£87.30**
- Subscription first month £79 → **£71.10**

You can create one Stripe Coupon (e.g. “10% off once”) and use it whenever a customer has a valid referral (e.g. came from a ref link or has `referred_by_customer_id` set).

---

## How to make referral codes work in Stripe

**Option A – Stripe “promo code” field (customer enters code)**
1. In Stripe Dashboard: **Products → Coupons** create a coupon (e.g. 10% off, once).
2. Create a **Promotion code** that uses that coupon (e.g. code `FRIEND10`).
3. In the app, when creating the Checkout Session, set `allow_promotion_codes=True`.
4. Customers see “Add promotion code” on the Stripe checkout page and can type e.g. `FRIEND10`. You’d tell referrers to share that code (or a unique code per referrer if you create multiple promotion codes).

**Option B – Apply discount automatically when referred** ✅ **Implemented**
1. In Stripe Dashboard: **Products → Coupons** → create a coupon (e.g. 10% off, duration “once”) and copy the Coupon ID (e.g. `coupon_xxx`).
2. Set `STRIPE_REFERRAL_COUPON_ID=coupon_xxx` in your environment (e.g. Railway).
3. The app applies this coupon when creating the Checkout Session if the customer has a valid referral (ref in URL or logged-in with `referred_by_customer_id`). Use duration “once” so it only applies to the first payment.

**Referrer reward (10% off next billing period per referral)** ✅ **Implemented**
- When a **referred friend** (customer with `referred_by_customer_id` set) completes a captions payment, the **referrer** gets +1 “referral discount credit”.
- When the **referrer**’s own captions subscription invoice is created, we apply 10% off to that invoice and use one credit. So: 1 referral → 10% off their next 1 billing period; 2 referrals → 10% off their next 2 billing periods (no stacking: 10% twice, not 20% once).
- **Setup:** Run `database_referral_referrer_rewards.sql` in Supabase (adds `customers.referral_discount_credits` and table `referral_discount_redemptions`). In Stripe Dashboard → Developers → Webhooks → your endpoint, add the event **invoice.created** so we can apply the discount to the referrer’s invoice before it’s paid.

**Option C – Per-referrer promotion codes**
- Create a Stripe Promotion code per referrer (e.g. code = their referral_code) all backed by the same coupon. Then either:
  - Use Option A and have friends type the referrer’s code, or
  - Use Option B but look up the referrer’s Stripe promotion code and pass that in `discounts` when the session is created (so Stripe enforces one use per code if you want).

---

## Recommendation

- **Discount:** 10% off the first payment (one-off or first month of subscription).
- **Implementation:** Option B (apply coupon automatically when the customer was referred) so the friend doesn’t have to remember a code. Add `STRIPE_REFERRAL_COUPON_ID` (or a promotion code ID if you prefer) and in the captions checkout routes, if the customer is referred, pass `discounts=[{"coupon": "..."}]` (and ensure the coupon is “once” so it only applies to the first payment).

If you want, the next step is to add Option B in code (config + checkout session creation when referred).
