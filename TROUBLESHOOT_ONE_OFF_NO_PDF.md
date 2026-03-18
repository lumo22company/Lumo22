# One-off: No PDF email / Order not on account

## Order not showing on My Account

**Cause:** Orders are matched to your account by **email**. If the email stored on the order didn’t match your login email exactly (e.g. different casing like `Test@Example.com` vs `test@example.com`), the order wouldn’t appear.

**What we changed:**
- New orders now store `customer_email` in **lowercase**, so they always match the account.
- For **existing** orders (e.g. a test one-off created before this fix), run this once in Supabase SQL Editor:

```sql
-- Normalize existing customer_email to lowercase (run once)
UPDATE caption_orders
SET customer_email = LOWER(TRIM(customer_email))
WHERE customer_email IS NOT NULL
  AND customer_email != LOWER(TRIM(customer_email));
```

After running it, refresh your account page; the order should appear.

---

## PDF delivery email not received

After you submit the intake form, a background job generates the captions and sends the email. If you don’t get it:

1. **Check spam/junk** and “Promotions” (Gmail).
2. **Check Railway logs** (or your host’s logs) for that time:
   - `[Captions] Starting generation for order ...` — generation started.
   - `[Captions] Delivery email sent for order ...` — email was sent.
   - `[Captions] DELIVERY_FAILED order_id=... error=...` — generation or send failed (see the `error=` message).
   - `[Captions] Delivery email FAILED ...` — SendGrid reported a failure.

3. **Common causes:**
   - **ANTHROPIC_API_KEY** (or **OPENAI_API_KEY** if you use OpenAI) missing or invalid in Railway/host env → generation fails.
   - **SENDGRID_API_KEY** missing or wrong → email not sent.
   - SendGrid bounce/block or invalid “from” address → delivery fails (see SendGrid Activity).

4. **If the order now appears on your account** (after the SQL fix above) but status is “Failed”, the delivery did fail; check logs for the exact error. You can re-run delivery by contacting support or (if you have a way) re-triggering generation for that order.
