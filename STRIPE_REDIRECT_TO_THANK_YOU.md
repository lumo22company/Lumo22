# Why you see the homepage after checkout — and how to fix it

After payment, Stripe sends the customer to the **"After payment"** URL that’s set on your **Payment link**. If that URL is your homepage (or blank), they’ll land on the homepage instead of the thank-you page.

---

## Fix: set the redirect to the thank-you page

1. Go to **Stripe Dashboard** → **Payment links** (or **Product catalog** → your product → the payment link).
2. Open the **payment link** you use for **30 Days Captions**.
3. Find **"After payment"** / **"Confirmation page"** / **"Redirect URL"**.
4. Set it to this **exact** URL (your Railway app):

   **https://lumo-22-production.up.railway.app/captions-thank-you**

   (No slash at the end. If you use a custom domain later, use that base + `/captions-thank-you`.)
5. **Save.**

Next time someone pays, they’ll land on the **thank-you page**, which then sends them to the intake form (or tells them to check their email for the intake link).

---

## If you use the Checkout flow (button goes to /api/captions-checkout)

When **STRIPE_SECRET_KEY** and **STRIPE_CAPTIONS_PRICE_ID** are set, the "Get my 30 days" button uses **Checkout** and the redirect is set in code — Stripe will send customers to your thank-you page with `?session_id=...`. You don’t need to set a redirect URL in the Payment link for that flow. If you still see the homepage, check that **BASE_URL** in Railway is correct (e.g. `https://lumo-22-production.up.railway.app` with no trailing slash).
