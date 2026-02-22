# Digital Front Desk — where you are and how to go live

## What’s already done

| Item | Status |
|------|--------|
| **Product & pricing** | Activate page with 3 plans (Starter £79, Standard £149, Premium £299), T&Cs, links to Stripe |
| **Payment** | Per-plan Stripe payment links in `.env` and (when set) on Railway |
| **After payment** | Stripe webhook sends customer welcome email with link to setup form |
| **Success page** | `/activate-success` — “You’re in” and check your email |
| **Setup form** | `/front-desk-setup` — business name, enquiry email, booking link → saved to Supabase |
| **Supabase** | `front_desk_setups` table with `forwarding_email` (you ran the SQL) |
| **Emails** | Customer gets their unique `reply-xxxxx@inbound.lumo22.com`; you get details + “Mark as connected” link |
| **Mark as connected** | `/front-desk-setup-done?t=TOKEN` updates status in DB |
| **SendGrid Inbound** | Destination URL and domain (inbound.lumo22.com) configured in SendGrid |
| **Inbound webhook** | `/webhooks/sendgrid-inbound` live on Railway, returns 200, processes email and sends auto-reply via OpenAI + SendGrid |
| **Pages** | `/digital-front-desk`, `/activate`, `/plans`; landing split section for Front Desk + Captions |

---

## What to confirm before calling it “live”

1. **DNS (inbound email)**  
   So that mail to `reply-xxxxx@inbound.lumo22.com` reaches SendGrid and your app:
   - In GoDaddy (or your DNS) you need an **MX** record for **inbound.lumo22.com** → `mx.sendgrid.net` (priority 10).
   - If you haven’t added it, do **Part B** in `STEP_2_SENDGRID_INBOUND_CHECKLIST.md`.

2. **Railway variables**  
   For the app (and auto-reply) to work in production, Railway must have:
   - `OPENAI_API_KEY`
   - `SENDGRID_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `FROM_EMAIL` (e.g. `hello@lumo22.com`)
   - `ACTIVATION_LINK_STARTER`, `ACTIVATION_LINK_STANDARD`, `ACTIVATION_LINK_PREMIUM` (or at least `ACTIVATION_LINK`)

3. **Stripe**  
   - **Test mode:** You can go “live” for real users with test cards and test webhooks; no change needed.
   - **Live mode:** When you’re ready to take real payments, in Stripe switch to live mode, create live payment links and (if needed) a live webhook, then set the live URLs/keys in Railway.

4. **Quick end-to-end test**  
   - Do a test payment (Starter/Standard/Premium).
   - Complete the setup form.
   - You get the email with the customer’s `reply-xxxxx@inbound.lumo22.com`.
   - Send an email to that address → you should get an auto-reply.

---

## Summary: “finished and live”

- **Finished:** When the checklist above is done (DNS MX, Railway vars, and one successful test).
- **Live:** When you’re happy to send customers to your site and to the activate/payment flow (test or live Stripe).

No code changes are required for this; it’s configuration and testing.

---

## Next: Chatbot option

You said you’d like to **offer the chatbot option** and set it up after. The site already has a **concierge** on the landing page (`#front-desk`): button-based flow (captions, consultation, questions, explore).  

When you’re ready, we can:
- Add a **chatbot** as part of the Digital Front Desk product (e.g. a widget customers can use on their site), or
- Extend the existing Lumo 22 concierge (e.g. AI-backed replies, or routing to Front Desk signup),

depending on what you mean by “offer the chatbot option.” We can define that once Digital Front Desk is live.
