# Digital Front Desk — set success URL in Stripe

After a customer pays for Digital Front Desk, Stripe redirects them to the **success URL** you set on each Payment Link.

## What to do

1. In **Stripe Dashboard** → **Payment links** → open each of your three links (Starter, Standard, Premium).
2. Click **Edit** (or the link settings).
3. Under **After payment** / **Success URL**, set:
   - **Production:** `https://lumo22.com/activate-success`
   - **Test:** `http://localhost:5001/activate-success` (for local testing) or your Railway URL: `https://lumo-22-production.up.railway.app/activate-success`
4. Save.

Then when a customer completes payment they’ll land on your “You’re in” page, and they’ll also receive the automatic welcome email from the webhook.
