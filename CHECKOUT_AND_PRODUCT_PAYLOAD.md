# Checkout & product payload

This document describes the product structure and the data that checkout (and future API/backend) should support.

## Product structure

- **Email Automation (Digital Front Desk)** — core flagship product. Email only; does **not** include chat by default.
- **Chat Assistant** — £59/month. Can be bought standalone or as an add-on (bundle = tier + £59, 5% off).
- **Bundle** — Email plan + Chat add-on. Add-on price by email tier: Starter +£25, Standard +£35, Premium +£45.

## Checkout payload (intended)

When building a Checkout Session or recording a purchase, the payload should support:

| Field | Type | Description |
|-------|------|-------------|
| `product_type` | `"email"` \| `"chat"` \| `"bundle"` | Whether the purchase is email-only, chat-only, or bundle. |
| `email_plan` | `"starter"` \| `"standard"` \| `"premium"` \| `null` | Set when product_type is email or bundle. |
| `chat_plan` | `"starter"` \| `"growth"` \| `"pro"` \| `null` | Set for **standalone** chat only; not used for add-on (add-on features scale with email tier). |
| `chat_addon` | `true` \| `false` | True when the purchase includes chat as an add-on to email (bundle). |
| `calculated_monthly_price` | number | Total monthly price in GBP. |

## Chat setup steps — when they appear

- **Standalone Chat Assistant:** Chat setup steps **always** appear (chat-only flow).
- **Bundle (email + chat add-on):** Chat setup steps appear **only if** `chat_addon === true`.
- **Digital Front Desk (email only):** Chat setup steps **never** appear unless chat was explicitly purchased (e.g. as add-on in same session).

## Tier-based chat features

- **Standalone chat:** Same product and features as on [Chat Assistant](/website-chat) page (£59/month).
- **Chat as add-on:** Features are constrained by the linked Email Automation tier:
  - Starter Email → basic chat features  
  - Standard Email → mid-tier chat features  
  - Pro Email → full chat feature set  

Copy used on pricing: *"Chat features scale with your selected email plan."*

## Current implementation

Checkout today uses **Stripe Payment Links** per product/tier:

- Email: `ACTIVATION_LINK_STARTER`, `ACTIVATION_LINK_STANDARD`, `ACTIVATION_LINK_PREMIUM`
- Email + chat bundle: `ACTIVATION_LINK_STARTER_BUNDLE`, `ACTIVATION_LINK_STANDARD_BUNDLE`, `ACTIVATION_LINK_PREMIUM_BUNDLE`
- Standalone chat: `CHAT_PAYMENT_LINK_STARTER`, `CHAT_PAYMENT_LINK_GROWTH`, `CHAT_PAYMENT_LINK_PRO` (fallback: `CHAT_PAYMENT_LINK`)

To support the full payload (e.g. for analytics or dynamic Checkout Sessions), the front end can set `data-product-type`, `data-email-plan`, `data-chat-addon`, `data-calculated-price` on the continue-to-payment button or form, and a future backend can read these when creating a Stripe Session or recording the sale.
