# Next steps – do these in order

Everything below is written so you can follow it step by step. Tick each box when done (change `[ ]` to `[x]`).

---

## Step 1: Reply Handler (Make.com) – when someone replies to your AI email ✅ DONE

**Why:** Right now your first scenario sends the first email. When a lead *replies* to that email, nothing happens. This second scenario makes the AI reply back.

### 1.1 Create the scenario

- [x] Go to **Make.com** and click **Create a new scenario**.
- [x] Name it: **AI Receptionist - Reply Handler**.

### 1.2 Add Gmail Watch

- [x] Click the **+** button.
- [x] Search **Gmail** → choose **Gmail** → **Watch Emails**.
- [x] Connect your Gmail (the same one that sends your AI emails).
- [x] Set **Criteria:** `Unread messages`, **Folder:** `Inbox`.
- [x] Click **OK**.

### 1.3 Add a filter (so you don’t reply to yourself)

- [x] Hover over the **line** between Gmail and the next module. Click the **funnel** icon.
- [x] **Filter name:** `Ignore my own emails`.
- [x] **Condition:**
  - **Left:** mapping → **Gmail → From Email** (the email address, not “From Name”).
  - **Operator:** `does not contain`.
  - **Right:** type the Gmail address you send AI emails from (e.g. `you@gmail.com`).
- [x] Click **OK**.

### 1.4 Add OpenAI

- [x] Click the circle on the right of the Gmail module → **Add another module**.
- [x] Search **OpenAI** → **Create a Chat Completion**.
- [x] Connect your OpenAI account (use the same API key as in your `.env` if asked).
- [x] **Model:** `gpt-4o-mini`.
- [x] **Messages** – add two items:

**Message 1 (System):**  
- Role: **System**.  
- Text – copy and paste this exactly:

```
You are an AI receptionist continuing an email conversation.
Be helpful and professional.
Never say you are an AI.
Never ask for a phone call.
Guide them to activation if appropriate.
```

**Message 2 (User):**  
- Role: **User**.  
- Text: click the mapping icon and choose **Gmail → Body Text** (so the AI sees the reply content).

- [x] Click **OK** on the OpenAI module.

### 1.5 Add Gmail Send

- [x] Click the circle on the right of the OpenAI module → **Add another module**.
- [x] **Gmail** → **Send an Email**.
- [x] **To:** mapping → **Gmail → From Email**.
- [x] **Subject:** mapping → **Gmail → Subject** (keeps “Re:” threading).
- [x] **Body type:** If you see “Collection of contents” or “RAW HTML”, choose **RAW HTML**. Map the AI output into the body – it will display correctly even when the AI returns plain text.
- [x] **Body:** mapping → **OpenAI → Choices → 1 → Message → Content** (or **OpenAI → Result** if that’s what you see). If you don’t see it, run the scenario once, then map it.
- [x] Click **OK**.

### 1.6 Turn it on and test

- [x] **Save** the scenario.
- [x] Turn the scenario **ON** (switch at bottom).
- [x] Set **scheduling:** e.g. every 15 minutes (or 1–5 mins on paid).
- [x] Test: submit your Typeform → wait for first AI email → reply to it (e.g. “How much does this cost?”) → wait for the schedule (or run once) → check you get an AI reply.

---

## Step 2: Payment / activation link (link to your website = better UX) ✅ DONE

**Why:** You link to your **website** (e.g. `/activate`); that page shows the Stripe button. One place to update the payment link, and a nicer experience than a raw Stripe URL in the email.

### 2.1 Stripe (recommended)

- [x] Go to **https://stripe.com** and sign up / log in.
- [x] Complete verification (business details, bank if required).
- [x] In dashboard: **Products** → **Add product**.
- [x] Create **one product** to start (you can add more later):

| Field      | Value                          |
|-----------|----------------------------------|
| Name      | AI Receptionist - Standard       |
| Price     | 149 GBP, Recurring, Monthly      |
| (optional)| Short description if you want   |

- [ ] Save the product.
- [ ] On the product page: **…** → **Create payment link** (or **Payment links** in the menu → Create link → select this product).
- [ ] Optional: enable “Collect customer information” so you get their email.
- [ ] **Copy the payment link** (e.g. `https://buy.stripe.com/xxxxx`) and save it.

### 2.2 Put the Stripe link on your site (one place to update)

- [ ] Open your project’s **`.env`** file.
- [ ] Add (or edit): `ACTIVATION_LINK=https://buy.stripe.com/xxxxx` with your real Stripe link.
- [ ] Save. Your site’s **/activate** page will show an “Activate now” button that goes to Stripe. Change the link later in `.env` only — no need to edit Make.com.

### 2.3 In the AI email, link to your website (not to Stripe)

- [ ] In **Make.com**, open the **first scenario** (Google Sheets → OpenAI → Gmail), not the Reply Handler.
- [ ] Click the **OpenAI** module that generates the email.
- [ ] Find the **System** or **User** message where the email text is defined.
- [ ] At the end, add (use your real website URL + `/activate`):

```
Activate your AI receptionist here: https://YOUR-WEBSITE.com/activate

No calls needed. Just activate and go live.
```

- [ ] Replace `https://YOUR-WEBSITE.com` with your actual site (e.g. `https://lumo22.com` or your deployed URL). The email link must go to **your site’s /activate page**, not to Stripe.
- [ ] Save the module and the scenario.

### 2.4 Test

- [ ] Run the app (`python3 app.py`) and open **http://localhost:5001/activate**. You should see “Activate now” and clicking it should go to Stripe.
- [ ] Submit your Typeform; open the first AI email. The link should be to your website’s activate page.
- [ ] Click it: you land on your site, then “Activate now” → Stripe checkout (you don’t have to pay).

---

## Step 3: Client onboarding (after payment)

**Why:** After someone pays, you want their details (business name, booking link, etc.) and to send a welcome email. This uses a second Typeform + sheet + one Make scenario.

### 3.1 Onboarding form and sheet

- [ ] Create a **new Typeform** (or duplicate and edit): name it e.g. “Client Onboarding”.
- [ ] Add questions: Email, Business Name, Booking Link (Calendly/Fresha/etc.), anything else you need.
- [ ] In **Google Sheets**, create a new sheet tab or file: **Active Clients**.
- [ ] In Typeform: connect the form to this sheet (Typeform’s “Connect” → Google Sheets). Columns will match your questions.

### 3.2 Redirect after payment

- [ ] In **Stripe**: edit your payment link (or product) → **After payment** → set **Redirect URL** to your onboarding Typeform’s share link (e.g. `https://form.typeform.com/to/xxxxx`). So: pay → then land on the form.

### 3.3 Make.com: when a new client is added

- [ ] In **Make.com**, create a new scenario: e.g. **Client onboarding**.
- [ ] Trigger: **Google Sheets** → **Watch Rows** → select your **Active Clients** sheet.
- [ ] Add **Google Sheets** → **Update a Row** (optional): update your main leads sheet with the new client’s booking link if you store that there.
- [ ] Add **Gmail** → **Send an Email**: To = new row’s Email, subject e.g. “You’re in – next steps”, body = short welcome + what happens next.
- [ ] Save and turn the scenario **ON**.

### 3.4 Test

- [ ] Do a test payment (or use Stripe test mode).
- [ ] Complete the onboarding form.
- [ ] Check the new row appears in **Active Clients** and that the welcome email was sent.

---

## Quick recap

| Step | What you did |
|------|------------------|
| 1    | Second Make scenario: Gmail Watch → filter → OpenAI → Gmail Send (replies get an AI reply). |
| 2    | Stripe product + payment link; link added to your first AI email in Make.com. |
| 3    | Onboarding Typeform + Active Clients sheet + Make scenario + Stripe redirect after payment. |

When all three are done, you have: first email → replies answered by AI → payment link in email → onboarding after payment → welcome email. If you want, we can add a “Go live” checklist (e.g. turn on scenarios, share Typeform, first outreach) as Step 4.
