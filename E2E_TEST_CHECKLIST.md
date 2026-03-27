# End-to-End Test Checklist

## Tests I Can Run for You (Automated)

Run this command locally:
```bash
pytest test_remediation_security.py test_system.py test_referral_discount.py test_intake_add_platform_visibility.py test_subscription_charges.py test_upgrade_flows.py test_intake_prefill_and_subscription.py -v
```

**What it covers:**
- Auth required for export-data, intake-link-by-email, billing endpoints
- 500 template exists
- Webhooks return 200
- Pack download uses date_str (no NameError)
- Home and captions pages load
- Delete account requires login
- System imports, config, Supabase connection
- Referral discount logic
- Intake template and upgrade-required flow
- Subscription charges and upgrade flows

**Result:** 35 tests — all passed ✅

---

## Tests You Need to Run Manually (Browser / Real Services)

### 1. One-Off Purchase Flow
- [ ] Go to /captions
- [ ] Click checkout (one-off)
- [ ] Complete Stripe payment (use test card `4242 4242 4242 4242`)
- [ ] Land on thank-you page — see intake link within ~5–10 seconds
- [ ] Click "Fill out form now" — form loads (no login needed)
- [ ] Submit form — see success message
- [ ] Check email — receive captions PDF within ~5–15 minutes

### 2. Subscription Purchase Flow
- [ ] Go to /captions
- [ ] Select subscription
- [ ] Complete Stripe checkout
- [ ] Thank-you page → intake form
- [ ] Submit form
- [ ] Create account (if prompted)
- [ ] Check email for captions

### 3. Logged-In Account Flow
- [ ] Log in
- [ ] Visit /account — see subscription(s) and packs
- [ ] Click "Manage billing" — Stripe portal opens
- [ ] Click "Edit form" — intake form loads prefilled
- [ ] Save changes — see success
- [ ] Download captions (if delivered) — PDF downloads

### 4. Billing Auth (Remediation)
- [ ] **Without logging in:** Try to change subscription (e.g. reduce platforms) from intake form — should get error / redirect to login
- [ ] **After logging in:** Change subscription — should succeed

### 5. Intake Link by Email (Remediation)
- [ ] **Without login:** On thank-you page, enter email in fallback — should get "Please log in" message
- [ ] **With login:** Enter matching email — should get intake link

### 6. Data Export (Remediation)
- [ ] Log in
- [ ] Visit `https://yoursite.com/api/auth/export-data` in browser (or curl with session cookie)
- [ ] Should see JSON with account + orders

### 7. Error Pages
- [ ] Visit `/nonexistent-page` — see 404 page
- [ ] (Hard to trigger) 500 — should show "Something went wrong" HTML, not raw JSON

### 8. Stripe Webhook
- [ ] After a test payment, confirm intake email arrives (webhook ran)
- [ ] Or use Stripe Dashboard → Developers → Webhooks → your endpoint → "Send test webhook" (checkout.session.completed)

### 9. Cron (if using reminders)
- [ ] Call `/api/captions-send-reminders?secret=YOUR_CRON_SECRET`
- [ ] Should return 200 with JSON (not 401)

---

## Quick Smoke Test (5 min)

1. Load `/` and `/captions`
2. Log in
3. Visit `/account`
4. Run: `pytest test_remediation_security.py -v`
