# Phase 2: Payment/Activation Setup - Step by Step

Set up payment links so clients can activate and pay without any calls.

---

## Overview

**Goal:** Clients can click a link, pay, and activate instantly - no calls needed.

**What you'll do:**
1. Create Stripe account (or Gumroad)
2. Create subscription products (£79/£149/£299)
3. Get payment links
4. Add activation link to your AI emails

**Time:** 20 minutes

---

## Option A: Stripe (Recommended)

### Step 1: Create Stripe Account

1. Go to https://stripe.com
2. Click **"Start now"** or **"Sign up"**
3. Enter your details:
   - Email
   - Full name
   - Country: United Kingdom
4. Verify your email
5. Complete business details:
   - Business type: Individual/Sole trader (or your business type)
   - Business name (or your name)
   - Address
6. Add bank account details (for payouts)

**Note:** Stripe will verify your account - this can take a few minutes to 24 hours.

---

### Step 2: Create Products in Stripe

1. **Go to Stripe Dashboard**
   - Log in to https://dashboard.stripe.com
   - Click **"Products"** in the left menu

2. **Create Product 1: Starter Plan**
   - Click **"Add product"**
   - **Name:** `AI Receptionist - Starter`
   - **Description:** `AI receptionist for small businesses - up to 100 enquiries/month`
   - **Pricing:**
     - **Price:** `79`
     - **Currency:** `GBP` (£)
     - **Billing:** `Recurring`
     - **Interval:** `Monthly`
   - Click **"Save product"**

3. **Create Product 2: Standard Plan** (Your main one)
   - Click **"Add product"** again
   - **Name:** `AI Receptionist - Standard`
   - **Description:** `Full AI receptionist replacement - up to 300 enquiries/month`
   - **Pricing:**
     - **Price:** `149`
     - **Currency:** `GBP` (£)
     - **Billing:** `Recurring`
     - **Interval:** `Monthly`
   - Click **"Save product"**

4. **Create Product 3: Premium Plan**
   - Click **"Add product"** again
   - **Name:** `AI Receptionist - Premium`
   - **Description:** `Unlimited enquiries for busy clinics and multi-staff businesses`
   - **Pricing:**
     - **Price:** `299`
     - **Currency:** `GBP` (£)
     - **Billing:** `Recurring`
     - **Interval:** `Monthly`
   - Click **"Save product"**

---

### Step 3: Create Payment Links

1. **For Standard Plan** (your main one):
   - Go to your **Standard** product
   - Click **"..."** (three dots) → **"Create payment link"**
   - **OR** go to **"Payment links"** in left menu → **"Create payment link"**
   - Select your **Standard** product
   - **Settings:**
     - **Collect customer information:** Enable (so you get their email)
     - **After payment:** Leave as default (or set redirect URL if you have onboarding form)
   - Click **"Create link"**
   - **Copy the payment link** - it will look like: `https://buy.stripe.com/xxxxx`
   - **Save this link** - you'll add it to your AI emails

2. **Optional:** Create links for Starter and Premium too (for later use)

---

## Option B: Gumroad (Simpler Alternative)

### Step 1: Create Gumroad Account

1. Go to https://gumroad.com
2. Click **"Start selling"** or **"Sign up"**
3. Enter your details and verify email

### Step 2: Create Products

1. Click **"Products"** → **"New product"**
2. **Product Type:** Select **"Subscription"**
3. **Product Name:** `AI Receptionist - Standard`
4. **Price:** `£149/month`
5. **Description:** Add your product description
6. Click **"Save"**
7. **Copy the product link** - it will look like: `https://yourname.gumroad.com/l/xxxxx`

---

## Step 4: Update Your AI Email Prompt

Now add the activation link to your initial AI email (the one that sends when someone submits your Typeform).

### Find Your Initial Email Scenario

1. Go to Make.com
2. Find your **first scenario** (the one that sends initial emails, not the reply handler)
3. Click on it to open

### Update OpenAI Module

1. Click on your **OpenAI module** (the one that generates the initial email)
2. Find the **System message** or **User message** that contains the email template
3. **Update the ending** to include your activation link

**Find this part in your prompt:**
```
End the email with:
"You've just interacted with our AI receptionist system..."
```

**Replace with:**
```
End the email with:
"You've just interacted with our AI receptionist system. This is exactly how your customers would experience it.

Activate your AI receptionist here: [YOUR STRIPE/GUMROAD LINK]

No calls needed. No setup calls. Just activate and go live."
```

**Replace `[YOUR STRIPE/GUMROAD LINK]`** with your actual payment link.

**Example:**
```
Activate your AI receptionist here: https://buy.stripe.com/xxxxx
```

4. Click **OK** to save

---

## Step 5: Test the Payment Flow

1. **Submit your Typeform** with a test email
2. **Wait for the initial AI email** to arrive
3. **Check the email:**
   - Does it contain your activation link?
   - Is the link clickable?
4. **Click the link:**
   - Does it take you to Stripe/Gumroad checkout?
   - Can you see the product details?
   - Does the price show correctly (£149/month)?

**Note:** Don't complete the payment in test mode - just verify the link works.

---

## Step 6: Update Your Reply Handler (Optional)

You can also add the activation link to your reply handler so if someone asks about pricing, the AI can provide the link.

1. Go to your **Reply Handler scenario**
2. Open the **OpenAI module**
3. In the **System message**, add:
   ```
   If they ask about pricing, provide the activation link: https://buy.stripe.com/xxxxx
   ```
4. Save

---

## Quick Reference: Your Payment Links

Save these somewhere safe:

- **Starter (£79/month):** `https://buy.stripe.com/xxxxx`
- **Standard (£149/month):** `https://buy.stripe.com/xxxxx` ← Main one
- **Premium (£299/month):** `https://buy.stripe.com/xxxxx`

---

## What Happens After Payment

**Right now:** Client pays → That's it (you'll need to manually activate them)

**Later (Phase 3):** Client pays → Automatically redirected to onboarding form → System activates automatically

For now, you can manually activate clients after they pay. Phase 3 will automate this.

---

## Troubleshooting

**"Stripe account not verified"**
- Complete all verification steps
- Add bank account details
- Wait 24 hours if needed

**"Payment link not working"**
- Make sure product is set to "Active" in Stripe
- Check the link is copied correctly
- Test in incognito mode

**"Link not showing in email"**
- Check your OpenAI prompt includes the link
- Make sure you saved the module
- Test by submitting Typeform again

---

## ✅ Completion Checklist

- [ ] Stripe/Gumroad account created
- [ ] Products created (at least Standard £149/month)
- [ ] Payment link copied and saved
- [ ] Activation link added to initial AI email prompt
- [ ] Tested - link appears in email
- [ ] Tested - link goes to checkout page
- [ ] Ready to accept payments!

---

## Next Steps After Phase 2

Once payment is set up:
1. ✅ Phase 2 Complete!
2. **Phase 3:** Create client onboarding (optional - can do manually at first)
3. **Phase 5:** Final testing
4. **Phase 6:** Go live and start outreach

**You're almost ready to start getting paid clients!** 🎉

---

## Pro Tip

Start with just the **Standard plan (£149/month)** link in your emails. You can add tier selection later once you have clients. Keep it simple for now!
