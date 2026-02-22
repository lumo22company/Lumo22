# Railway Variables — What to Add (Step 4)

In Railway → your service → **Variables**, add each row below.  
**Name** = the key. **Value** = copy from your `.env` file on your Mac (or use the value shown in the “Value” column).

| Name | Value (where to get it) |
|------|-------------------------|
| FLASK_ENV | `production` |
| FLASK_DEBUG | `False` |
| SECRET_KEY | Copy from your `.env` (same as SECRET_KEY) |
| OPENAI_API_KEY | Copy from your `.env` |
| SUPABASE_URL | Copy from your `.env` |
| SUPABASE_KEY | Copy from your `.env` |
| SENDGRID_API_KEY | Copy from your `.env` |
| FROM_EMAIL | Copy from your `.env` (e.g. hello@lumo22.com) — must be verified in SendGrid |
| FROM_NAME | Optional. Sender display name in Gmail/inbox (default: Lumo 22) |
| CAPTIONS_PAYMENT_LINK | Copy from your `.env` (Stripe payment link; fallback if checkout not used) |
| STRIPE_SECRET_KEY | Copy from your `.env` (Stripe secret key sk_test_ or sk_live_ — for redirect to intake after payment) |
| STRIPE_CAPTIONS_PRICE_ID | Copy from your `.env` (Stripe Price ID price_xxx — from Stripe → Products → 30 Days Captions) |
| STRIPE_WEBHOOK_SECRET | Copy from your `.env` (starts with whsec_) |
| BASE_URL | Your Railway URL from “Generate domain” — e.g. https://something.up.railway.app (no slash at the end) |

Optional (only if you use them):

| Name | Value |
|------|--------|
| BUSINESS_NAME | Copy from your `.env` or leave blank |
| ACTIVATION_LINK | Copy from your `.env` if you use the activate page |

---

**How to use this:**  
1. Open your `.env` file in LUMO22 on your Mac.  
2. In Railway Variables, for each **Name** in the table, add a new variable and paste the **Value** from your `.env` (or use the literal value shown, e.g. `production` for FLASK_ENV).  
3. For **BASE_URL**, use the exact URL Railway gave you when you clicked Generate domain (no trailing slash).
