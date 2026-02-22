# 30 Day Captions — How customers create an account

## Process and flow

1. **Customer pays** for 30 Day Captions (one-off or subscription) → Stripe checkout.
2. **Stripe webhook** creates a caption order and sends an **intake-link email** to the customer’s email (from Stripe).
3. **Customer** opens the link in that email: `/captions-intake?t=TOKEN`.
4. **Customer** fills the intake form → clicks **Next step** → **Send details**.
5. **On success** the page shows:
   - “Request received. We'll take it from here — your captions will arrive by email within a few minutes.”
   - Below that: **“Create an account to access your captions and more in one place.”**
   - A **Create account** box: the **email is pre-filled** (from their order, hidden) and they only enter a **password** (min 6 characters) and click **Create account**.
6. **Create account** → `POST /api/auth/create-account` with `{ email, password }`. Backend creates the customer record (same email as the order), logs them in (session), returns success.
7. **Page** shows “Account created! Go to your account” with a link to **/account**.
8. **On /account** (customer dashboard) they see:
   - **30 Days Captions** section with their caption order(s).
   - For each **delivered** order: **Download captions**, **Edit form**, **Contact us**.
   - **Manage subscription** (if they have a subscription).
   - Digital Front Desk / Chat setups (if any) and Settings.

So account creation is **optional for one-off** and **required for subscription**: after they submit the intake form, subscription customers see a message that they must create an account to manage their subscription; one-off customers see the same success screen with an optional create-account box. The account uses the **same email** as the order so their caption orders appear on the dashboard and they can re-download or edit the form.

## Mandatory account for subscribers

- When the order is a **subscription** (has `stripe_subscription_id`), the success screen shows: *"Your captions are on the way. Create an account to manage your subscription, re-download captions, and cancel anytime."* and a note: *"Required for subscription customers — you'll use this to manage billing and re-download captions."*
- The create-account box is shown with the email pre-filled; they set a password and click Create account. There is no “skip” or “done” state that implies they’re finished without an account.
- **One-off** customers still see the original message and the create-account box as optional.

## What was edited

- **Create account button reliability:** The submit handler for the create-account form is now in the same (first) script block as Next step / Edit / Send details, so the **Create account** button works even if the rest of the form script doesn’t run.
- **Clarity:** The success screen now shows which email the account will be created for (read-only), so customers know they’re using the same address their captions are sent to.

## Optional future improvements

- **Thank-you page:** The post-payment thank-you page could mention “You’ll get an email with a form link; after you submit it you can create an account to access your captions anytime.”
- **Intake-link email:** Could add one line: “After you submit the form you can create an account to download your captions again from one place.”
