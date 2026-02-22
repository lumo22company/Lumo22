# Captions reminder – steps 3 & 4

## 3. Add `invoice.paid` to Stripe webhook ✓ DONE

Added via Stripe API. Your webhook at `https://lumo-22-production.up.railway.app/webhooks/stripe` now receives:
- `checkout.session.completed`
- `invoice.paid`

## 4. Daily reminders ✓ DONE

Reminders run **inside your main app** at 9am UTC daily (APScheduler). No separate Railway cron service needed. The endpoint `/api/captions-send-reminders` is still available for manual runs or external cron if you prefer.

---

**Step 2 already done:** `CRON_SECRET` is in your `.env` and has been added to Railway via `railway variables set`.

---

**Deploy (no Git):** Run `railway up` from your project folder to deploy. See **DEPLOY_AND_SEE_CHANGES.md**.
