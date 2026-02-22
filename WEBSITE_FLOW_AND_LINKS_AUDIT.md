# Website flow and links audit

Audit date: 2025-02. Purpose: map routes → templates → links, find errors and irrelevant links, suggest edits.

---

## 1. Route map (what exists)

| URL | Route in app.py | Template | Notes |
|-----|-----------------|----------|--------|
| `/` | ✅ index() | landing.html | Main public landing |
| `/captions` | ✅ | captions.html | 30 Days Captions product |
| `/captions-intake` | ✅ | captions_intake.html | Your details form (?t= token) |
| `/captions-thank-you` | ✅ | captions_thank_you.html | Post-payment |
| `/captions-checkout` | ✅ | captions_checkout.html | Pre-checkout (one-off) |
| `/captions-checkout-subscription` | ✅ | captions_checkout_subscription.html | Pre-checkout (subscription) |
| `/terms` | ✅ | terms.html | Terms & Conditions |
| `/plans` | ✅ redirect | → digital_front_desk#pricing | OK |
| `/digital-front-desk` | ✅ | digital_front_desk.html | DFD product |
| `/book` | ✅ redirect | → digital_front_desk | OK (no template links to /book) |
| `/website-chat` | ✅ | website_chat.html | Chat product |
| `/website-chat-success` | ✅ | website_chat_success.html | Post-chat payment |
| `/signup` | ✅ | customer_signup.html | **Customer** signup (DFD/Chat/Captions) |
| `/login` | ✅ | customer_login.html | **Customer** login |
| `/forgot-password` | ✅ | forgot_password.html | Password reset request |
| `/reset-password` | ✅ | reset_password.html | Set new password (?token=) |
| `/account` | ✅ | customer_dashboard.html | Unified customer dashboard |
| `/dashboard` | ✅ redirect | → account | OK |
| `/form` | ✅ redirect | → index (/) | Lead form removed |
| `/activate` | ✅ | activate.html | DFD plan selection → Stripe |
| `/activate-success` | ✅ | activate_success.html | Post-DFD payment |
| `/front-desk-setup` | ✅ | front_desk_setup.html | DFD/chat setup (?t=, product=) |
| `/front-desk-setup-done` | ✅ | front_desk_setup_done.html | Mark connected (link from email) |
| `/webhook-test` | ✅ | webhook.html | Internal/test |
| `/outreach` | ✅ | outreach_dashboard.html | Internal |
| **/business/login** | ❌ **none** | — | **404** |
| **/business/signup** | ❌ **none** | — | **404** |
| **/business/dashboard** | ❌ **none** | — | **404** |
| **/admin/clients** | ❌ **none** | — | **404** |
| **/admin/** (any) | ❌ **none** | — | **404** |

---

## 2. Errors and problems

### 2.1 Broken routes (404)

- **/business/login**, **/business/signup**, **/business/dashboard**  
  - Templates **business_login.html**, **business_signup.html**, **business_dashboard.html** exist and link to these URLs (and to each other).  
  - No route in `app.py` serves these pages, so every link to them returns **404**.  
  - These look like a legacy “business/API user” flow (lead-capture dashboard) that was never wired to the app.

- **/admin/clients**, **/admin/** (any)**  
  - **admin_landing.html**, **admin_home.html**, **admin_clients.html** link to e.g. `/admin/clients` and “Manage Clients”.  
  - No `/admin/*` routes in `app.py` → **404**.

### 2.2 Unused templates (dead code)

- **index.html** – No route renders it. `/` serves **landing.html**. So `index.html` is unused (likely an old per-client lead form).
- **login.html** – Not used. `/login` serves **customer_login.html**. This file calls `/api/business/login` and redirects to `/dashboard` (old business flow).
- **signup.html** – Not used. `/signup` serves **customer_signup.html**. Same pattern: business API + `/dashboard`.
- **business_login.html**, **business_signup.html**, **business_dashboard.html** – No routes; any visit or link to `/business/*` 404s.
- **admin_landing.html**, **admin_home.html**, **admin_clients.html** – No routes; any link to `/admin/*` 404s.

### 2.3 Misleading or inconsistent links

- **business_dashboard.html** (if it were ever served):  
  - “View Lead Form” → `/form`. `/form` redirects to `/` (landing), not a dedicated lead form. So the label is misleading.  
  - “Digital Front Desk & Captions” → `/account`. That’s the **customer** account; in a “business” dashboard context it can be confusing.

- **Double redirect after customer login/signup**:  
  - **customer_login.html** redirects to `next` or `/account` (correct).  
  - **customer_signup.html** redirects to `/account` (correct).  
  - The unused **login.html** / **signup.html** redirect to `/dashboard`, which then redirects to `/account`. Only relevant if something ever pointed at the wrong template; for the live flow, no change needed.

### 2.4 Anchor links (verified)

- **digital_front_desk.html**: `id="pricing"` and `id="chat-assistant"` exist.  
- Links to `/digital-front-desk#pricing` and `/digital-front-desk#chat-assistant` are valid.

---

## 3. Customer-facing flow (correct)

- **Landing** (`/`) → Captions / Digital Front Desk / Pricing → **Captions** → checkout or subscription → thank-you → **Your details** (captions-intake) or email link.  
- **Landing** → **Digital Front Desk** → **Activate** → Stripe → activate-success → front-desk-setup (from email).  
- **Landing** → **Website Chat** → payment → website-chat-success.  
- **Nav/footer**: Login / Sign up → **customer_login** / **customer_signup** → **account** (customer_dashboard).  
- **Account** → captions-intake (with token), billing portal, front-desk-setup links, DFD/Captions product links.  
- **Forgot/reset password** → email link → reset-password → login.  
- **Terms** linked from checkout and footer; **Contact** = mailto.  

All of the above use routes that exist and templates that are actually rendered.

---

## 4. Suggested edits

### 4.1 Fix broken links (choose one strategy)

**Option A – Remove references to non-existent pages**

- In any template that might still link to **/business/login**, **/business/signup**, **/business/dashboard** (e.g. if you ever reuse fragments from business_*.html), remove those links or point them to existing pages (e.g. `/login`, `/signup`, `/account`).
- In **admin_landing.html**, **admin_home.html**, **admin_clients.html**: remove or change links to **/admin/clients** and **/admin/** until you have real admin routes (e.g. point to `/` or a “coming soon” page, or remove the links).

**Option B – Add minimal routes so links don’t 404**

- Add routes in `app.py` for **/business/login**, **/business/signup**, **/business/dashboard** that render **business_login.html**, **business_signup.html**, **business_dashboard.html** (and fix **business_dashboard** “View Lead Form” → either a real form URL or remove the link).
- Add routes for **/admin** and **/admin/clients** that render **admin_landing.html** and **admin_clients.html** (and protect them with auth if needed).

Recommendation: if you are not using the “business” or “admin” flows, **Option A** is simpler and avoids maintaining unused pages.

### 4.2 Clean up dead templates (optional)

- **index.html**, **login.html**, **signup.html**: either delete or clearly mark as legacy/unused so no one adds links to them. If you need a per-client lead form later, that should be a dedicated route (e.g. `/client/<id>/form`) and template, not reusing `index.html` without a route.
- **business_*.html** and **admin_*.html**: if you choose Option A and don’t plan to use them, move to a `/templates/legacy/` or delete; otherwise implement routes (Option B).

### 4.3 Small improvements

- **customer_login.html**: Already redirects to `next` or `/account`. No change required.
- **customer_signup.html**: Already redirects to `/account`. No change required.
- **Footer/nav**: All links point to existing routes; no edits needed for correctness.
- **captions_checkout** / **captions_checkout_subscription**: “Next step” → `/api/captions-checkout` and `/api/captions-checkout-subscription` are correct (they redirect to Stripe).

### 4.4 Summary table of suggested actions

| Item | Action |
|------|--------|
| Links to /business/login, /business/signup, /business/dashboard | Remove or replace with /login, /signup, /account (unless you add routes) |
| Links to /admin/clients or /admin/* | Remove or replace until admin routes exist |
| business_dashboard “View Lead Form” → /form | Change to “Home” or remove; /form only redirects to / |
| Unused templates (index, login, signup, business_*, admin_*) | Delete or move to legacy; avoid new links to them |
| customer_login / customer_signup redirect | No change (already correct) |
| Footer & main nav | No change (all valid) |

---

## 5. Quick reference: where each template is used

| Template | Served by route? | Used in flow |
|----------|------------------|---------------|
| landing.html | ✅ `/` | Main site |
| captions.html | ✅ `/captions` | Captions product |
| captions_intake.html | ✅ `/captions-intake` | Your details form |
| captions_thank_you.html | ✅ `/captions-thank-you` | After Captions payment |
| captions_checkout.html | ✅ `/captions-checkout` | Pre-checkout one-off |
| captions_checkout_subscription.html | ✅ `/captions-checkout-subscription` | Pre-checkout subscription |
| terms.html | ✅ `/terms` | Legal |
| digital_front_desk.html | ✅ `/digital-front-desk` | DFD product |
| website_chat.html | ✅ `/website-chat` | Chat product |
| website_chat_success.html | ✅ `/website-chat-success` | After chat payment |
| customer_signup.html | ✅ `/signup` | Customer signup |
| customer_login.html | ✅ `/login` | Customer login |
| customer_dashboard.html | ✅ `/account` | Customer account |
| forgot_password.html | ✅ `/forgot-password` | Request reset |
| reset_password.html | ✅ `/reset-password` | Set new password |
| activate.html | ✅ `/activate` | DFD plan → Stripe |
| activate_success.html | ✅ `/activate-success` | After DFD payment |
| front_desk_setup.html | ✅ `/front-desk-setup` | DFD/chat setup |
| front_desk_setup_done.html | ✅ `/front-desk-setup-done` | Mark connected |
| 404.html | ✅ error handler | 404 page |
| index.html | ❌ | Unused |
| login.html | ❌ | Unused (legacy business) |
| signup.html | ❌ | Unused (legacy business) |
| business_login.html | ❌ | No route → 404 |
| business_signup.html | ❌ | No route → 404 |
| business_dashboard.html | ❌ | No route → 404 |
| admin_landing.html | ❌ | No route → 404 |
| admin_home.html | ❌ | No route → 404 |
| admin_clients.html | ❌ | No route → 404 |

If you tell me whether you want to keep the business/admin flows or drop them, I can suggest exact template edits (and, if needed, minimal routes) next.
