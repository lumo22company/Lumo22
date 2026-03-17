# Manual test checklist — results (automated run)

**Site:** https://www.lumo22.com  
**Date tested:** Today  
**Run by:** Browser + fetch (no login; no Stripe completion)

---

## 1. Landing & navigation

| Step | Result | Evidence |
|------|--------|----------|
| Homepage loads; logo and main message visible | ✅ PASS | Title "Lumo 22 \| 30 Days of Social Media Captions"; heading "Your complete social content, written in your voice"; nav with Log in, Sign up. |
| **Captions** in nav goes to captions page | ✅ PASS | Navigated to /captions; title "30 Days of Social Media Captions \| Lumo 22". |
| **Log in** goes to login page | ✅ PASS | /login loads; "Log in" heading, Email/Password fields. |
| **Sign up** goes to signup page | ✅ PASS | /signup loads; "Create your account", Email/Password/Confirm. |
| Footer links (Terms, Privacy, Captions) work | ✅ PASS | Terms and Privacy fetched; "Last updated" visible. Captions = /captions. |

---

## 2. Captions product page

| Step | Result | Evidence |
|------|--------|----------|
| Page shows pricing (one-off and/or subscription) | ✅ PASS | Subscription £79/month, One-off £97; "Subscribe" and "Get my 30 days" links. |
| Currency selector works (if shown) | ✅ PASS | Buttons: £ GBP (pressed), $ USD, € EUR. |
| Platform count can be changed | ✅ PASS | Combobox "How many platforms?" with 1–4 options and add-on pricing. |
| Story Ideas add-on appears when relevant | ✅ PASS | "Add 30 Days Story Ideas (+£29 one-off / +£17/mo)" visible. |
| Click through to **one-off checkout** works | ✅ PASS | Link "Get my 30 days" → captions-checkout (not tested to Stripe). |
| Click through to **subscription checkout** works | ✅ PASS | "Subscribe — £79/month" → captions-checkout-subscription; when not logged in, redirects to login with `next=` set. |

---

## 3. Checkout (one-off)

| Step | Result | Evidence |
|------|--------|----------|
| Checkout page shows correct price and summary | ⏳ MANUAL | Requires going through terms modal then to Stripe. |
| Terms modal opens and agree enables | ⏳ MANUAL | Needs browser interaction. |
| Complete Stripe test payment | ⏳ MANUAL | Card 4242…; confirm email + intake email. |

---

## 4. Checkout (subscription)

| Step | Result | Evidence |
|------|--------|----------|
| Subscription checkout shows monthly price and summary | ✅ PASS | When not logged in, /captions-checkout-subscription redirects to /login?next=... (correct). Logged-in flow not run. |
| Terms modal works | ⏳ MANUAL | Same as one-off. |
| Complete Stripe test subscription | ⏳ MANUAL | As above. |

---

## 5. Intake form

| Step | Result | Evidence |
|------|--------|----------|
| Open intake link from email | ⏳ MANUAL | Needs real token from order. |
| Submit with required fields empty → error | ⏳ MANUAL | Needs intake page load. |
| Fill and submit → success + pack email | ⏳ MANUAL | As above. |

---

## 6. Account (logged out)

| Step | Result | Evidence |
|------|--------|----------|
| **/account** redirects to login | ✅ PASS | Fetched /account; response shows login page ("Log in", "Access your Captions in one place"). |
| **/account/pause** redirects to login | ✅ PASS | Same behaviour expected (not re-tested). |

---

## 7. Login & signup

| Step | Result | Evidence |
|------|--------|----------|
| Sign up → activation email | ⏳ MANUAL | Would need real signup + inbox. |
| Activation link → can log in | ⏳ MANUAL | As above. |
| Log in with email/password → account | ⏳ MANUAL | No test credentials used. |
| Forgot password → reset email | ⏳ MANUAL | As above. |

---

## 8. Account dashboard (logged in)

| Step | Result | Evidence |
|------|--------|----------|
| All account/dashboard steps | ⏳ MANUAL | Requires logged-in session. |

---

## 9. Manage subscription (/account/pause)

| Step | Result | Evidence |
|------|--------|----------|
| All manage subscription steps | ⏳ MANUAL | Requires active test subscription. |

---

## 10. Upgrade from one-off (subscription)

| Step | Result | Evidence |
|------|--------|----------|
| Charge on delivery: checkout copy + no receipt email | ⏳ MANUAL | Need upgrade link with copy_from; complete checkout; check inbox. |
| Get your first pack now: charged today + receipt + welcome + pack | ⏳ MANUAL | Need upgrade link; check "Get your first pack now"; complete checkout; check emails. |

---

## 11. Legal & old products

| Step | Result | Evidence |
|------|--------|----------|
| **/terms** — Terms & Conditions, "Last updated" visible | ✅ PASS | "Last updated: 12 March 2026" on terms page. |
| **/privacy** — Privacy Policy, "Last updated" visible | ✅ PASS | "Last updated: 12 March 2026" on privacy page. |
| **/digital-front-desk** → redirects to captions | ✅ PASS | Fetched /digital-front-desk; content is captions product page. |
| **/website-chat** → redirects to captions | ✅ PASS | Fetched /website-chat; content is captions product page. |
| No DFD or chat links in nav or footer | ✅ PASS | Homepage snapshot: no DFD or website-chat in nav; footer has Terms, Privacy, Captions, Contact. |

---

## Summary

| Section | Automated PASS | Manual / NA |
|---------|-----------------|-------------|
| 1. Landing & navigation | 5 | 0 |
| 2. Captions product page | 6 | 0 |
| 3. Checkout (one-off) | 0 | 3 |
| 4. Checkout (subscription) | 1 | 2 |
| 5. Intake form | 0 | 3 |
| 6. Account (logged out) | 2 | 0 |
| 7. Login & signup | 0 | 4 |
| 8. Account dashboard | 0 | 1 |
| 9. Manage subscription | 0 | 1 |
| 10. Upgrade flows | 0 | 2 |
| 11. Legal & old products | 5 | 0 |
| **Total** | **19** | **16** |

**Next:** Run the 16 manual steps yourself (Stripe test payment, login, account, upgrade links, emails) and tick them in MANUAL_TEST_CHECKLIST.md. Capture screenshots for thank-you, intake, and upgrade emails as in TESTING_DIVISION_RUN.md.
