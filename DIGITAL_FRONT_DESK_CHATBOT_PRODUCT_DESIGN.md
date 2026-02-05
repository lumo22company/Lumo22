# Digital Front Desk — Chatbot Product Design (Sale-Ready)

**Purpose:** Define the **website chatbot** as a sellable product so it can be marketed, priced, and built in one coherent go.

---

## 1. Product name and positioning

| Item | Choice |
|------|--------|
| **Product name** | **Front Desk Chat** (or "Website Chat" in UI) |
| **One-liner** | *"An AI chat on your website that answers questions and sends visitors to book — same brain as your email front desk."* |
| **Place in lineup** | Add-on to Digital Front Desk (email) — one product, two channels: **Email** + **Website chat** |

**Why it fits:**
- Same value prop as Front Desk (instant reply, qualification, booking) but on the site where visitors already are.
- Reuses business context (name, services, booking link) and existing OpenAI + setup data.
- Competitors sell "chatbot" and "receptionist" separately; you sell **one receptionist, two channels**.

---

## 2. Target customer and job-to-be-done

- **Who:** Same as Front Desk — solo/small businesses, salons, clinics, therapists, trades.
- **Job:** "When someone is on my website I want them to get an instant, helpful answer and be sent to book or contact, without me being there."
- **Outcome:** More leads and bookings from website traffic; fewer bounces; one consistent tone (email + chat).

---

## 3. Core features (v1 — sale-ready)

| Feature | Description |
|---------|-------------|
| **Embeddable widget** | One script tag (or copy-paste snippet) customer adds to their site. Chat bubble + conversation UI. |
| **AI with business context** | Replies use business name, enquiry email, booking link, and optional "about your business" from setup. |
| **Same behaviour as email** | Polite, concise, British English; suggests booking or contact when relevant; no emojis/hype. |
| **Lead capture** | If visitor shares email (or we get it from "book" CTA), create lead and/or send thread to enquiry inbox so it’s in one place. |
| **Usage and limits** | Count chat "conversations" or "messages" per month; tie to existing plan limits (e.g. 100/300/unlimited) or a separate chat allowance. |

**Explicitly out of v1:** Custom branding, multiple widgets, chat history UI for the business, SMS from chat. (Can add later.)

---

## 4. Pricing and packaging

**Recommended: include in plan, don’t create a fourth tier.**

| Plan | Email | Website chat |
|------|--------|----------------|
| **Starter £79** | ✓ Up to 100 enquiries/mo | ✗ Not included |
| **Standard £149** | ✓ Up to 300 enquiries/mo | ✓ Included (e.g. up to 200 chat conversations/mo) |
| **Premium £299** | ✓ Unlimited | ✓ Included (e.g. unlimited or 500+ chats) |

**Alternative:** Add-on for any plan: **+£29/month** "Website Chat" — then Starter can add it too.

**Recommendation:** Include in **Standard and Premium** only. Use "Website chat" as a differentiator and upsell from Starter.

**Copy for pricing table:**
- Starter: "—" or "Add-on available"
- Standard: "✓ Website chat widget"
- Premium: "✓ Website chat widget"

---

## 5. Customer journey (sale → live)

1. **Awareness** — Landing / plans page: "Email + website chat" and "Try the concierge" (existing).
2. **Purchase** — Same as now: choose plan → Stripe → success → setup email.
3. **Setup** — Same form: business name, enquiry email, booking link. **Add:**  
   - Optional: "About your business (for chat)" text area (services, tone, FAQs).  
   - **If Standard/Premium:** Show "Your website chat" section with embed code and "Enable chat" toggle.
4. **Go live** — Customer pastes script on their site; chat is live. Email continues as now (forwarding address, etc.).
5. **Ongoing** — Chats and emails both count toward plan limits; leads appear in same place (existing lead tracking when built).

---

## 6. What to build (implementation scope)

### 6.1 Data and config

- **front_desk_setups** (or equivalent):  
  - `chat_enabled` (boolean, default false).  
  - `chat_widget_key` (unique, e.g. UUID or nanoid) — used in embed and API.  
  - Optional: `business_description` or `chat_instructions` (text) for AI context.
- **Chat usage:** Either count "conversations" in a new table (e.g. `front_desk_chat_sessions`) or count messages; enforce limits in API.

### 6.2 Embeddable widget

- **Script:** e.g. `https://your-domain.com/widget.js` or `embed.js` with query param `key=WIDGET_KEY`.
- **Behaviour:** Loads a small bubble; on open, shows welcome + messages; input sends to your API; renders bot replies; optional "Book here" / "Email us" buttons.
- **Styling:** Minimal (one primary colour or use CSS vars) so it fits most sites. Optional: let customer set accent colour in setup later.

### 6.3 Backend API

- **POST /api/chat** (or `/api/front-desk/chat`):  
  - Body: `{ "widget_key": "...", "message": "user message", "history": [{ "role": "user"|"assistant", "content": "..." }] }`.  
  - Auth: widget_key only (no login).  
  - Look up setup by widget_key; check plan and usage limits; call OpenAI with business context + history; return assistant message.  
  - Optionally create/update session and store message for lead/analytics.
- **OpenAI:** Same style as `inbound_reply_service` — system prompt with business name, booking link, enquiry email, optional business description; user message + history.

### 6.4 Setup / activation UI

- **Setup form (post-payment):**  
  - If plan is Standard or Premium: show "Website chat" section.  
  - Toggle "Enable website chat".  
  - Text area: "About your business (optional)" for AI.  
  - Display embed code: `<script src="https://.../embed.js" data-key="WIDGET_KEY"></script>`.
- **Optional:** Simple "Front Desk dashboard" page (later) with same embed code, usage, and toggle.

### 6.5 Limits and overage

- Define "conversation" (e.g. one open chat thread per visitor per day = 1 conversation).  
- In API: before calling OpenAI, check monthly count for this setup; if over limit, return a friendly "limit reached" message or upgrade CTA.  
- No need for overage billing in v1 — just soft cap and message.

---

## 7. Messaging and copy (sale-ready)

### 7.1 Product page (digital_front_desk.html)

- **Subhead or bullet:** "Email + website chat — one AI receptionist, two ways to reach you."
- **Feature list:** Add "Website chat widget — visitors get instant answers and can book from your site."
- **Compare table:** Add row "Website chat" — Starter: —; Standard: ✓; Premium: ✓.

### 7.2 One-liner for ads/outreach

- "Digital Front Desk: AI that replies to every email and chats on your website — and sends everyone to book."

### 7.3 Embed / setup screen

- **Title:** "Your website chat"  
- **Short description:** "Add this script to your website. Visitors can ask questions and get instant replies, and you’ll see leads in the same place as email."

---

## 8. Launch checklist (sale-ready)

- [ ] **Positioning:** Chat is part of Digital Front Desk (Standard/Premium or add-on), not a separate product.
- [ ] **Pricing:** Decision: included in Standard+Premium vs add-on; update pricing table and Stripe if add-on.
- [ ] **Copy:** Product page, compare table, and setup section updated (this doc has the lines).
- [ ] **Data:** Migration for `chat_enabled`, `chat_widget_key`, optional `business_description`/`chat_instructions`.
- [ ] **API:** POST /api/chat with widget_key, limits, OpenAI with business context.
- [ ] **Widget:** Embed script + minimal UI (bubble, thread, input, optional Book/Email CTA).
- [ ] **Setup:** Embed code and toggle in existing setup flow (and optional dashboard later).
- [ ] **Usage:** Count conversations (or messages); enforce plan limits; friendly message when over.
- [ ] **Leads:** Decide how chat leads merge with email (same table, same "Mark as connected" flow if applicable).

Once the above are done, the **Digital Front Desk chatbot product is ready for sale** as "Front Desk Chat" (or "Website Chat") on the existing plans page and activation flow.

---

## 9. Future-proofing (do not build yet)

Leave clear TODOs for when you implement:

- **Chat widget embed instructions** — Copy-paste snippet, `data-key` or equivalent, in setup/dashboard.
- **API key / widget key management** — For standalone chat customers (£59) and for Front Desk (Standard/Premium) chat.
- **Per-seat or per-conversation limits** — Enforce by plan (e.g. 200 chat conversations/mo Standard, higher or unlimited Premium; standalone £59 tier TBD).
- **Annual billing toggle** — e.g. "Pay yearly, save X%" on pricing/activate; no Stripe or logic changes until ready.
