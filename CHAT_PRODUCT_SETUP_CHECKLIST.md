# Website Chat Product — Setup Checklist

The chat product is wired in code as a **separate add-on** (or bundle feature). Digital Front Desk plans are email-only; chat is not included in any plan. See **DIGITAL_FRONT_DESK_AND_CHAT_PRODUCT_RULES.md** for product rules and future technical enforcement (e.g. chat requires active Front Desk or bundle).

---

## 1. Run the database migration

In **Supabase** → SQL Editor → New query, paste and run the contents of:

**`database_front_desk_chat.sql`**

This adds: `product_type`, `chat_enabled`, `chat_widget_key`, `business_description` to `front_desk_setups`.

---

## 2. Create the Stripe product and Payment Link

1. **Stripe Dashboard** → Products → **Add product**
   - **Name:** `Website Chat Widget`
   - **Description:** `Chat widget for your website — £49/month. No full inbox.`
   - **Pricing:** Recurring, £49, GBP, Monthly

2. After saving, open the product → **Add another price** (or use the default price).

3. **Payment Links** → **New** (or create from the product’s “Create payment link”):
   - Product: Website Chat Widget (£49/month)
   - **Success URL (chat only):** `https://lumo-22-production.up.railway.app/website-chat-success`  
     (Use your live BASE_URL + `/website-chat-success`. Do **not** use `/activate-success` — that’s for Digital Front Desk.)

   You don’t need to add metadata. The webhook recognises the chat product by the amount (£49 = 4900 pence). If you ever create the link via the Stripe API, you can optionally set `metadata[product]=chat` for extra clarity.

4. Copy the **Payment Link** URL (e.g. `https://buy.stripe.com/...`).

---

## 3. Set the payment link in your environment

**Local (`.env`)** — already set to:

```env
CHAT_PAYMENT_LINK=https://buy.stripe.com/test_8x2eVcejge5f6Xi1jW6Vq04
```

**Railway** — In your project: **Variables** → **New variable** (or edit existing):

- **Name:** `CHAT_PAYMENT_LINK`
- **Value:** `https://buy.stripe.com/test_8x2eVcejge5f6Xi1jW6Vq04`

Save and redeploy so the app picks up the new variable.

---

## 4. Webhook behaviour

The existing **Stripe webhook** (`/webhooks/stripe`) already handles the chat product:

- **Detection:** `amount_total` = **4900** (£49) in GBP. (Optional: if you create the Payment Link via API, you can set `metadata.product` = `chat` as well.)
- **Action:** Creates a pending chat-only row in `front_desk_setups` and sends the customer an email with a link to complete setup:  
  `https://your-domain.com/front-desk-setup?product=chat&t=TOKEN`

No extra webhook or endpoint is required.

---

## 5. Customer flow (after payment)

1. Customer pays £49 (Stripe Payment Link).
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
| 1 | Run `database_front_desk_chat.sql` in Supabase |
| 2 | Create Stripe product “Website Chat Widget” £49/month and a Payment Link |
| 3 | Set `CHAT_PAYMENT_LINK` in `.env` and production env |
| 4 | Test: pay with test card → check email → complete setup → see embed code |

After that, the chat product is live on the site and ready to sell.
