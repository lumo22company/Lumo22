# Lumo 22 — Email setup

We use **Lumo 22 (SendGrid)** for billing and product emails. **Stripe** should send only failed-payment emails.

## Stripe Dashboard: turn off these customer emails

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → **Settings** (gear icon) → **Customer emails**
2. Turn **OFF**:
   - Successful payments
   - Invoice paid (for subscriptions)
   - Subscription updated
   - Subscription canceled
3. Turn **ON** (keep):
   - Failed payments / Payment action required

This avoids duplicate or competing emails. Lumo 22 handles receipts, plan changes, and cancellations with branded, tailored content.

---

## Who sends what

| Trigger | Sent by | Subject / purpose | Price included? |
|---------|---------|-------------------|-----------------|
| After checkout (one-off or sub) | **Lumo 22** | Order receipt — thanks, product summary, intake link coming | Yes |
| Intake link ready | **Lumo 22** | Link to complete intake form | Order summary only |
| Intake submitted | **Lumo 22** | Captions delivery (PDF attached) | No |
| Pre-pack reminder (subscription) | **Lumo 22** | Update form before next pack | No |
| Add Story Ideas | **Lumo 22** | Plan change — what changed, new price (was old) | Yes |
| Reduce plan | **Lumo 22** | Plan change — what changed, new price (was old) | Yes |
| Plan change (Stripe portal) | **Lumo 22** | Plan change — what changed, new price (was old) | Yes |
| Subscription cancelled | **Lumo 22** | Subscription cancelled — access until end of period | No |
| Failed payment | **Stripe** | Payment failed / action required | Yes |
| Signup | **Lumo 22** | Welcome + verify email | No |
| Password reset | **Lumo 22** | Password reset link | No |
| Email change | **Lumo 22** | Confirm new email | No |

---

## Summary

| Category | Sender |
|----------|--------|
| Billing (receipt, plan change, cancelled) | Lumo 22 |
| Product (intake link, delivery, reminder) | Lumo 22 |
| Auth (welcome, password, email change) | Lumo 22 |
| Failed payment | Stripe |

---

## Verification

All email templates have been verified to produce non-empty content. Run:

```bash
python3 scripts/verify_all_emails.py
```

To regenerate sample HTML files for preview:

```bash
python3 scripts/generate_email_samples.py
# Open email_samples/index.html in a browser
```
