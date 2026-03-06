# Uncommitted changes — what’s in each file

Everything below is **only on your machine**. The live site does not have these changes until we commit and push.

---

## 1. Domain & redirects (fix thank-you 404, Stripe URLs)

| File | What changed |
|------|----------------|
| **app.py** | `redirect_bare_domain_to_www`: redirect `lumo22.com` → `www.lumo22.com` so Stripe success URL works |
| **api/captions_routes.py** | `_base_url_for_redirect()`: use `https://www.lumo22.com` when BASE_URL is bare domain so checkout success/cancel URLs don’t 404 |

---

## 2. Captions flow: intake, thank-you, emails

| File | What changed |
|------|----------------|
| **app.py** | Intake prefill only when `upgraded_from_token == copy_from` (no prefill after account delete + resubscribe). Pass `prefilled_primary` for Primary platform dropdown. Add `back_to_captions_url`, `add_stories_url` / `add_platforms_url` with `#pricing` and currency. Subscribe URL includes `currency`. |
| **api/captions_routes.py** | Intake-link API: create order from Stripe session if webhook hasn’t run; `_send_intake_email_for_order`; return `is_subscription`; use `_base_url_for_redirect()`. Delivery email uses explicit HTML. |
| **api/webhooks.py** | Webhook: store `currency`, `upgraded_from_token`; use BASE_URL for intake URL; send intake email via `send_intake_link_email(..., order)` with order summary. |
| **services/notifications.py** | `_captions_delivery_email_html`, `_intake_link_email_html`, `_build_intake_order_summary`, `send_intake_link_email(to, url, order)`; delivery email no “reply for changes” line. |
| **templates/captions_thank_you.html** | Polling, fallback “enter email” UI, “Fill out form now” / “I’ll do it later”, conditional “manage your subscription” text, styling. |
| **templates/captions_intake.html** | Primary platform preselection, “Back to form”, “Back to your account” when logged in, goal “Other”, upgrade CTA at bottom with business name, error text black, no “Get my 30 days” in nav, etc. |

---

## 3. Checkout & upgrade flow

| File | What changed |
|------|----------------|
| **app.py** | `subscribe_options` (one per one-off order) for multiple upgrade buttons; `add_stories_url` / subscription checkout includes `copy_from` when present. |
| **api/captions_routes.py** | Subscription checkout: `copy_from` in metadata; success/cancel use `_base_url_for_redirect()`. |
| **templates/captions_checkout.html** | Log In styling, terms button yellow/swipe, “Back to Captions” removed, etc. |
| **templates/captions_checkout_subscription.html** | Upgrade notice (yellow on black), terms button style, spacing, “Back to Captions” removed, `back_to_captions_url`, etc. |
| **templates/captions.html** | Prefill from URL, `copy_from` preserved in subscription link. |

---

## 4. Account & auth

| File | What changed |
|------|----------------|
| **app.py** | `subscribe_options` in account context; no DFD/setups; `get_by_customer_email_including_stripe_customer` for orders. |
| **api/auth_routes.py** | Preferences: 500 and clearer error when marketing opt-in save fails. |
| **services/caption_order_service.py** | `get_by_customer_email_including_stripe_customer()` so orders by same Stripe customer show in account. |
| **services/customer_auth_service.py** | (Likely marketing opt-in / preferences.) |
| **templates/customer_dashboard.html** | Already committed in last push (swipe buttons, View 30 Days Captions removed, etc.). If you have new edits here they’re in this list. |

---

## 5. PDFs & captions content

| File | What changed |
|------|----------------|
| **services/caption_generator.py** | Story prompts: “Idea:”, “Suggested wording:”, “Story hashtags:” format; higher max_tokens. |
| **services/caption_pdf.py** | Stories parser for multi-line content; caption PDF day heading = “DAY N — THEME” only (no caption preview). |

---

## 6. Shared UI: nav, footer, terms

| File | What changed |
|------|----------------|
| **templates/_footer.html** | Footer logo image above “Lumo 22”. |
| **templates/_terms_modal.html** | Scroll hint text white. |
| **templates/_terms_content.html** | (Terms content tweaks if any.) |
| **static/css/style.css** | Footer logo styles. |

---

## 7. Other templates (nav/layout/consistency)

| File | What changed |
|------|----------------|
| **templates/404.html** | Nav/layout. |
| **templates/activate.html** | Nav. |
| **templates/activate_success.html** | Nav. |
| **templates/change_email_confirm.html** | Nav. |
| **templates/customer_signup.html** | Nav/layout. |
| **templates/digital_front_desk.html** | Nav. |
| **templates/forgot_password.html** | Nav. |
| **templates/front_desk_setup.html** | Nav. |
| **templates/login_success.html** | Nav. |
| **templates/reset_password.html** | Nav. |
| **templates/terms.html** | Nav. |
| **templates/website_chat_success.html** | Nav. |

---

## 8. Scripts, config, docs (optional to commit)

| File | What changed |
|------|----------------|
| **.env.example** | Env var list / comments. |
| **BRAND_STYLE_GUIDE.md** | Doc tweaks. |
| **LAUNCH_TEST_ANALYSIS.md** | Restructure. |
| **NOT_RECEIVING_EMAIL_AFTER_CHECKOUT.md** | Extra troubleshooting. |
| **scripts/audit_stripe_prices.py** | Small fixes. |
| **scripts/check_deployment.sh** | Small fixes. |
| **static/js/chat-widget.js** | Minor. |
| **static/js/section-parallax.js** | Minor. |
| **static/js/split-parallax.js** | Minor. |
| **api/routes.py** | Tiny change. |
| **test_intake_business_name.py** | Test updates. |

---

## Summary

- **Sections 1–6** are the main product and UX fixes (domain, captions flow, checkout, account, PDFs, shared UI). **Recommend committing all of these** so the live site matches what you’ve been testing.
- **Section 7** is nav/layout consistency across pages; safe to include.
- **Section 8** is config/docs/scripts; commit if you want them in the repo (e.g. .env.example and docs are usually good to have).

If you want, we can commit **everything** in one go, or do **sections 1–7 only** and leave section 8 for a separate pass.
