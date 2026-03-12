# Launch Day Checklist — Lumo 22

Use this to run through site checks, bank setup, and pre-launch verification before you go live and move on to outreach.

---

## Morning: Bank & Stripe

### 1. Bank account (Stripe Connect / payouts)
- [ ] Add bank account in Stripe Dashboard → Settings → Payouts
- [ ] Verify account details; confirm test transfer if Stripe requests it
- [ ] Note: First payout can take 2–7 business days after first successful payment

### 2. Stripe live mode
- [ ] Switch to **Live** mode (toggle top-right in Dashboard)
- [ ] Re-check Customer emails (Billing settings): upcoming renewals OFF, finalised invoices OFF, failed payments ON
- [ ] Re-check Payment method updates: Stripe-hosted page
- [ ] Verify Statement descriptor (e.g. LUMO 22)
- [ ] Confirm Privacy policy and Terms URLs in Public details
- [ ] Ensure live API keys are in Railway (or your host) — no test keys in production

### 3. Stripe products (live)
- [ ] Confirm live Prices/Products for captions (one-off, subscription, extra platform, Stories)
- [ ] Confirm payment links or Checkout Session use live price IDs
- [ ] Test a £0.50 or minimum live charge, then refund, to validate live flow

---

## Midday: Site & flows

### 4. Core flows (manual test)
- [ ] **Landing** — Homepage and Captions page load; CTA goes to checkout or pricing
- [ ] **Checkout** — Select plan (1 platform, no Stories) → pay with real card (or small amount) → lands on thank-you
- [ ] **Order receipt** — Check inbox for order receipt email
- [ ] **Intake link** — Receive intake email; open link; complete form
- [ ] **Captions delivery** — Receive delivery email with PDF; open and confirm content
- [ ] **Account** — Sign up or log in; dashboard shows order; “Manage subscription” opens Stripe Customer Portal
- [ ] **Subscription** — If you have a live sub: “Edit form”, “Pause”, “Add Story Ideas” (or “Reduce”) behave as expected
- [ ] **Plan change email** — After a plan change, confirm email with “What changed” and pricing
- [ ] **Legal** — /terms and /privacy load and display correctly

### 5. Auth & emails
- [ ] **Signup** — New account → welcome + verify email → verify link works
- [ ] **Password reset** — Request reset → email arrives → link works
- [ ] **Intake reminder** — If you have a sub: cron sends pre-pack reminder (or trigger manually for testing)

### 6. Redirects & edge cases
- [ ] Old product URLs (e.g. /digital-front-desk) redirect to /captions
- [ ] 404 page works
- [ ] Mobile: key pages and checkout are usable on phone

---

## Afternoon: Admin & monitoring

### 7. Admin & monitoring
- [ ] Log into Railway (or host) and confirm app is running
- [ ] Stripe webhooks: Dashboard → Developers → Webhooks → live endpoint returns 2xx
- [ ] SendGrid: Check activity for recent sends; no bounces or blocks
- [ ] Optional: Set up simple uptime check (e.g. UptimeRobot) for lumo22.com

### 8. Final checks
- [ ] Currency selector (if used) shows correct prices for GBP/USD/EUR
- [ ] Refer-a-friend link (if used) works from account
- [ ] No test copy, placeholder text, or “lorem ipsum” on live pages
- [ ] Contact/support email (hello@lumo22.com) is correct everywhere

---

## Done

- [ ] All items above completed
- [ ] First live payment received and payout path verified
- [ ] You’re ready to launch and start outreach

---

## Next: Outreach / marketing (when ready)

1. Define audience (coaches, consultants, creatives, etc.)
2. Choose channels (email, LinkedIn, Instagram, etc.)
3. Build lead list or content plan
4. Create simple sequences (e.g. cold email → follow-up → CTA to lumo22.com/captions)
5. Set up basic tracking (link with UTM params, optional analytics)

---

*Last updated: Feb 2026*
