# Email wording reference

## Order receipt — implemented

Sent right after Stripe checkout, before the intake link. Wording:

**Subject:** Thanks for your order — 30 Days of Social Media Captions

**Body:**
> Hi,
>
> Thanks for your order. We've received your payment for 30 Days of Social Media Captions.
>
> You'll receive an email shortly with a link to complete your short intake form (about 2 minutes). Once you submit, we'll generate your captions and send them to you by email within a few minutes.
>
> If you don't see the intake email, check your spam folder or reply to this email and we'll help.
>
> — Lumo 22

---

## Stripe webhook: add `customer.subscription.updated`

For plan-change confirmation emails when customers upgrade/downgrade via the Stripe billing portal, add this event in Stripe:

1. Stripe Dashboard → Webhooks → your endpoint
2. Click "Select events"
3. Add **customer.subscription.updated**
4. Save
