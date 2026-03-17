# Lumo 22 — Manual test checklist (print this)

**Site:** https://www.lumo22.com (Stripe test mode)  
**Date tested:** _______________

---

## 1. Landing & navigation

- [ ] Homepage loads; logo and main message visible
- [ ] **Captions** in nav goes to captions page
- [ ] **Log in** goes to login page
- [ ] **Sign up** goes to signup page
- [ ] Footer links (Terms, Privacy, Captions) work

---

## 2. Captions product page

- [ ] Page shows pricing (one-off and/or subscription)
- [ ] Currency selector works (if shown)
- [ ] Platform count can be changed
- [ ] Story Ideas add-on appears when relevant
- [ ] Click through to **one-off checkout** works
- [ ] Click through to **subscription checkout** works (if available)

---

## 3. Checkout (one-off)

- [ ] Checkout page shows correct price and summary
- [ ] **Next step — read & accept terms** opens Terms modal
- [ ] Scroll to bottom of terms → **I have read and agree** button enables
- [ ] Cancel/close modal and try again
- [ ] Accept terms → redirects to Stripe (test payment)
- [ ] Complete Stripe test payment (card 4242 4242 4242 4242)
- [ ] Redirect back to success/thank-you; confirmation email received
- [ ] Intake form email received with link

---

## 4. Checkout (subscription)

- [ ] Subscription checkout shows monthly price and summary
- [ ] Terms modal works (same as above)
- [ ] Complete Stripe test subscription
- [ ] Redirect and confirmation email; intake email with link

---

## 5. Intake form

- [ ] Open intake link from email (or use test link with token)
- [ ] Form is pre-filled if editing existing order
- [ ] Submit with **required fields empty** → error at top, fields highlighted in red
- [ ] Fill all required fields and submit
- [ ] Success message; pack email arrives (one-off) or first pack (subscription)

---

## 6. Account (logged out)

- [ ] **/account** redirects to login
- [ ] **/account/pause** redirects to login

---

## 7. Login & signup

- [ ] **Sign up** → create account → activation email
- [ ] Click activation link → can log in
- [ ] **Log in** with email/password → lands on account/dashboard
- [ ] **Log out** → Account link no longer in nav
- [ ] **Forgot password** → reset email → new password works

---

## 8. Account dashboard (logged in)

- [ ] Account page shows 30 Days Captions section
- [ ] Past packs listed; **Download** opens/downloads PDF
- [ ] **Edit form** goes to intake (pre-filled)
- [ ] Referral section: **Copy link** copies to clipboard (if enabled)

---

## 9. Manage subscription (/account/pause)

*(Need an active test subscription.)*

- [ ] **Manage billing** opens Stripe Customer Portal
- [ ] **Pause for 1 month** → row shows “Paused” and **Resume subscription**
- [ ] **Resume subscription** → row returns to normal
- [ ] **Add Story Ideas** (if not included) → modal → confirm → row updates
- [ ] **Remove Story Ideas** → terms modal → scroll to bottom → accept → row updates
- [ ] **Get your pack sooner** opens first modal
  - [ ] **Use current details** → confirm modal with amount → Cancel (no charge)
  - [ ] **Update my form** → intake (pre-filled) → submit → yellow “Form updated” panel on return
  - [ ] On yellow panel, **Confirm and get my pack** → success message; pack email later
  - [ ] **Cancel** on panel goes back to Manage subscription

---

## 10. Upgrade from one-off (subscription)

*(Need a one-off order and upgrade link with `copy_from=TOKEN`, or use upgrade reminder email.)*

- [ ] **Charge on delivery:** Open subscription checkout (do **not** check “Get your first pack now”). Copy says “You won’t be charged today” and shows charge date. Complete checkout → thank-you; **only** “You’re set up — 30 Days Captions subscription” email (no “payment received” receipt).
- [ ] **Get your first pack now:** Open subscription checkout, check “Get your first pack now”. Copy says “You’ll be charged today”. Complete checkout → receipt email + “You’re subscribed” welcome; pack email arrives shortly after.

---

## 11. Legal & old products

- [ ] **/terms** — Terms & Conditions, “Last updated” visible
- [ ] **/privacy** — Privacy Policy, “Last updated” visible
- [ ] **/digital-front-desk** → redirects to captions
- [ ] **/website-chat** → redirects to captions
- [ ] No DFD or chat links in nav or footer

---

## Notes

_Use this space for bugs or issues:_

_____________________________________________________________________________

_____________________________________________________________________________

_____________________________________________________________________________

---

*Lumo 22 — captions-only site. Run this on live (Stripe test mode) or staging.*
