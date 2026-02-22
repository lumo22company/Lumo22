# Chat Assistant — Setup Checklist

The **Chat Assistant** is **£59/month** standalone. Bundles = **tier + £59 with 5% off** (£131 / £198 / £340). Digital Front Desk does **not** include chat by default. See **PRICING_STRUCTURE_NOTE.md** and **CHECKOUT_AND_PRODUCT_PAYLOAD.md**.

---

## 1. Run the database migration

In **Supabase** → SQL Editor → New query, paste and run the contents of:

**`database_front_desk_chat.sql`**

This adds: `product_type`, `chat_enabled`, `chat_widget_key`, `business_description` to `front_desk_setups`.

---

## 2. Create Stripe products and Payment Links

**Chat Assistant (standalone)** — one product, one price:

| Product        | Price/month | Env var               |
|----------------|-------------|------------------------|
| Chat Assistant | £59         | `CHAT_PAYMENT_LINK`    |

Create one Stripe product at £59/month and a Payment Link with **Success URL** = `{BASE_URL}/website-chat-success`. Set the link in **`CHAT_PAYMENT_LINK`**. Or run `scripts/create_chat_single_stripe_link.py`.

**Email + Chat bundle** — tier + £59 with 5% off:

| Bundle        | Tier + £59 | 5% off | Total  | Env var                          |
|---------------|------------|--------|--------|----------------------------------|
| Starter+chat  | £138       | £131   | £131  | `ACTIVATION_LINK_STARTER_BUNDLE` |
| Standard+chat | £208       | £198   | £198  | `ACTIVATION_LINK_STANDARD_BUNDLE`|
| Premium+chat  | £358       | £340   | £340  | `ACTIVATION_LINK_PREMIUM_BUNDLE` |

Create 3 Stripe products at £131, £198, £340/month. Success URL: `{BASE_URL}/activate-success`. Or run `scripts/create_bundle_stripe_links_discounted.py` (CHAT_PRICE=59, BUNDLE_DISCOUNT_PERCENT=5).

---

## 3. Set payment links in your environment

**Local (`.env`)** — at minimum:

```env
CHAT_PAYMENT_LINK=https://buy.stripe.com/...   # Chat Assistant £59/month
```

Optional (email + chat bundle):

```env
ACTIVATION_LINK_STARTER_BUNDLE=https://buy.stripe.com/...
ACTIVATION_LINK_STANDARD_BUNDLE=https://buy.stripe.com/...
ACTIVATION_LINK_PREMIUM_BUNDLE=https://buy.stripe.com/...
```

**Railway** — Add the same variables under your service → **Variables**. Redeploy after changes.

---

## 4. Webhook behaviour

The existing **Stripe webhook** (`/webhooks/stripe`) already handles chat and bundles:

- **Chat (standalone):** `amount_total` in GBP = **5900** (£59). Optional: set `metadata.product` = `chat` on the Payment Link.
- **Bundle (email + chat):** amounts **10400**, **18400**, **34400** (£104, £184, £344) — same flow as Front Desk (setup email, success URL `/activate-success`).
- **Action (chat standalone):** Creates a pending chat-only row in `front_desk_setups` and sends the customer an email with setup link:  
  `https://your-domain.com/front-desk-setup?product=chat&t=TOKEN`

No extra webhook or endpoint is required.

---

## 5. Customer flow (after payment)

1. Customer pays £59 (Stripe Payment Link).
2. Stripe redirects to your **chat** success URL (`/website-chat-success`).
3. Webhook runs → pending chat setup created → **email sent** with setup link.
4. Customer opens link → **chat-only setup form** (business name, enquiry email, booking link, about your business).
5. On submit → row updated with `chat_widget_key`, `chat_enabled` = true → **embed code** shown on the page.
6. Customer pastes the script tag on their site. The current **placeholder** widget shows a chat bubble; replace `static/js/chat-widget.js` with the full widget when you add **POST /api/chat**.

---

## 6. Optional: real chat replies (later)

When you’re ready to turn the widget into a live chat:

- Add **POST /api/chat** that accepts `widget_key`, `message`, `history`; looks up setup by `chat_widget_key`; calls OpenAI with business context; returns the reply.
- Replace **`static/js/chat-widget.js`** with the full UI that calls that API and renders the thread.

Until then, the embed code and placeholder bubble are enough for “ready to sell” and for testing the payment → email → setup → embed flow.

---

## Summary

| Step | Action |
|------|--------|
| 1 | Run `database_front_desk_chat.sql` in Supabase (if not done) |
| 2 | In Stripe: create Chat Assistant £59 and Payment Link; optionally create bundle links (£131 / £198 / £340) |
| 3 | Set `CHAT_PAYMENT_LINK` (and optionally bundle vars) in `.env` and Railway |
| 4 | Deploy to Railway so the live site has the new plans and Chat Assistant page |
| 5 | Test: pay with a test card → check redirect and (for chat) setup email → complete setup → see embed code |

After that, the Chat Assistant and bundles are live and ready to sell.
