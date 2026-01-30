# Steps to Sell 30 Days of Social Media Captions

Get the product on your website and start taking orders. Do these in order.

**Automated flow:** If you want payment → intake email → AI-generated captions → delivery email with no manual writing, see **AUTOMATION_SETUP.md** after completing Steps 1–2 below.

---

## 1. Add a Stripe Payment Link (so you get paid)

- [ ] Log in to [Stripe](https://dashboard.stripe.com).
- [ ] Go to **Product catalog** → **Add product**.
- [ ] Name: **30 Days of Social Media Captions**. Price: **£97** (or your price), one-time.
- [ ] Save, then open the product → **…** → **Create payment link** (or use **Payment links** in the sidebar → Create link → choose this product).
- [ ] Under **After payment**, set **Redirect URL** to your thank-you page:  
  `https://yourdomain.com/captions-thank-you`  
  (If you skip this, Stripe shows its own confirmation; you can add the page later.)
- [ ] Copy the payment link (e.g. `https://buy.stripe.com/xxxxx`).
- [ ] In your project root, open `.env` and add:
  ```env
  CAPTIONS_PAYMENT_LINK=https://buy.stripe.com/xxxxx
  ```
- [ ] Restart the app. The “Get my 30 days” button on the product page will now go to Stripe checkout.

**Why:** Customers can pay in one click. You get paid before you do the work.

---

## 2. Put the product on your website

You have two places where the offer lives:

**A. Landing page (`/`)**  
The 30 Days section is already there. The CTA can stay as “Get my 30 days” and either:
- Link to the **dedicated product page** (`/captions`) so people can read the full offer and then pay, or  
- Link straight to the **Stripe payment link** (after you set `CAPTIONS_PAYMENT_LINK`).

**B. Dedicated product page (`/captions`)**  
A full page with:
- Headline and one-liner  
- What’s included  
- Who it’s for / what problem it solves  
- How it works (3 steps)  
- Price and one clear CTA (Pay now / Get my 30 days)

**Done for you:** The template `templates/captions.html` and route `/captions` are in place. The landing CTA “Get my 30 days” links to `/captions`. On the product page, the button uses `CAPTIONS_PAYMENT_LINK` when set in `.env`; otherwise it falls back to the mailto link.

**Optional:** In the nav (landing and product page), add a “Captions” link to `/captions` so the offer is one click away.

---

## 3. Decide what happens after payment

When someone pays, you need their **email** (Stripe gives you that) and their **intake answers** (business, audience, voice, platform, goal).

**Option A — Email intake (simplest)**  
- After each sale, Stripe sends you a notification (or you check Stripe Dashboard).
- You email the client: “Thanks for your order. So we can tailor your 30 days, please answer the questions in this form: [link].”
- Link can be:
  - Your intake page: `https://yourdomain.com/captions-intake`, or  
  - A Typeform / Google Form you duplicate from `INTAKE_QUESTIONNAIRE.md`.
- Client submits; you get their answers by email or in a sheet. You write the captions and deliver.

**Option B — Intake before payment**  
- “Get my 30 days” goes to the intake page first; at the end, “Submit and pay” sends answers and redirects to Stripe.  
- Requires either saving intake to your backend and passing an ID to Stripe metadata, or a multi-step form (e.g. Typeform) that ends at the payment link. More setup; use later if you want.

**Recommended for now:** Option A. Payment first, then you send the intake link. No extra tech.

---

## 4. Set up the intake form

**If you use the on-site intake page (`/captions-intake`):**

- [ ] The page is live at `/captions-intake`. Link to it in your “after payment” email (e.g. “Please complete your intake: https://yourdomain.com/captions-intake”).
- [ ] Form submits by email (mailto) to the address you set in the template. If you prefer to collect in a spreadsheet or CRM, replace the form action with a Typeform/Google Form link or a small backend that saves submissions.

**If you use Typeform / Google Form:**

- [ ] Create a new form. Copy the questions from `products/30-days-social-captions/INTAKE_QUESTIONNAIRE.md`.
- [ ] Send the form link to the client after payment. No change to the website needed.

---

## 5. Deliver the captions

- [ ] Use the client’s intake answers and the framework in `PRODUCT_30_DAYS_SOCIAL_CAPTIONS.md` to write the 30 captions.
- [ ] Use the structure in `SAMPLE_DELIVERY_FORMAT.md`: one document per client, one caption per day, copy-paste friendly.
- [ ] Deliver by email: attach the document (`.md` or PDF) and a short note. Turnaround: state “3–5 business days” (or your actual SLA) on the product page and in the post-purchase email.

---

## 6. Optional: Thank-you page after payment

If you set Stripe’s “After payment” redirect to `/captions-thank-you`:

- [ ] Create a simple page: “Thanks for your order. We’ve received your payment. You’ll get an email from us within 24 hours with a short form so we can tailor your 30 days. If you have any questions, reply to that email.”
- [ ] Add route in `app.py`: `@app.route('/captions-thank-you')` and render a template. Keeps everything on your domain and sets expectations.

---

## Checklist summary

| Step | Action |
|------|--------|
| 1 | Create Stripe product + payment link, add `CAPTIONS_PAYMENT_LINK` to `.env` |
| 2 | Landing CTA: link to `/captions` or to Stripe; ensure `/captions` page looks right |
| 3 | After payment: email client with intake link (e.g. `/captions-intake` or Typeform) |
| 4 | Intake: use on-site form or external form; collect answers |
| 5 | Write 30 captions from framework; deliver as one document (3–5 days) |
| 6 | (Optional) Add `/captions-thank-you` and set as Stripe redirect |

Once 1–5 are done, the service is live and sellable. Add the thank-you page when you want a smoother post-payment experience.
