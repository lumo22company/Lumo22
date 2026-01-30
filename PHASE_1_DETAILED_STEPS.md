# Phase 1: Reply Handling - Copy & Paste Guide

This is a step-by-step guide with exact text to copy and paste. Follow each step in order.

---

## Step 1: Create New Scenario in Make.com

1. Go to https://www.make.com
2. Click **"Create a new scenario"** (big blue button)
3. Name it: **"AI Receptionist - Reply Handler"**
4. Click **"OK"**

You should now see a blank canvas with a **"+"** button.

---

## Step 2: Add Gmail Watch Module

1. Click the **"+"** button
2. Search for: **"Gmail"**
3. Select: **"Gmail"** → **"Watch Emails"**
4. **Connect your Gmail account** (if not already connected)
   - Click "Add" next to Connection
   - Sign in with Google
   - Authorize Make.com
5. **Configure the module:**
   - **Mailbox:** Select your Gmail account
   - **Filter:** Click "Set up a filter"
     - **Subject:** Contains → Type: **"Re:"**
     - Click **"Add another condition"**
     - **From:** Does not equal → Your email address
   - **Label:** (leave empty for now)
6. Click **"OK"**

**What this does:** Watches for email replies to your automated emails.

---

## Step 3: Add Safety Filter

1. Click the **circle** on the right of your Gmail module
2. Click **"Add another module"**
3. Search for: **"Filter"**
4. Select: **"Flow control"** → **"Filter"**
5. **Configure the filter:**
   - Click **"Add a condition"**
   - **Condition 1:**
     - Field: **{{Gmail → Body Text}}**
     - Operator: **Does not contain**
     - Value: **"unsubscribe"**
   - Click **"Add a condition"**
   - **Condition 2:**
     - Field: **{{Gmail → Body Text}}**
     - Operator: **Does not contain**
     - Value: **"opt out"**
   - Click **"Add a condition"**
   - **Condition 3:**
     - Field: **{{Gmail → From Email}}**
     - Operator: **Does not equal**
     - Value: **Your email address** (the one sending the AI emails)
6. Click **"OK"**

**What this does:** Prevents infinite loops and spam replies.

---

## Step 4: Add Google Sheets Lookup

1. Click the **circle** on the right of your Filter module
2. Click **"Add another module"**
3. Search for: **"Google Sheets"**
4. Select: **"Google Sheets"** → **"Get a Row"**
5. **Connect your Google account** (if not already connected)
6. **Configure the module:**
   - **Spreadsheet:** Select **"AI Receptionist Leads"** (your main sheet)
   - **Sheet:** Select the sheet tab (usually "Sheet1" or the one Typeform created)
   - **Search:** Click **"Set up a search"**
     - **Column:** Select **"Email"** (or whatever column has email addresses)
     - **Search Value:** Click the mapping icon → Select **{{Gmail → From Email}}**
   - Click **"OK"**
7. Click **"OK"** on the module

**What this does:** Finds the original lead data so the AI knows who it's talking to.

**Important:** Run the scenario once now to test this lookup works:
- Click **"Run once"** at the bottom
- If you have a test email in your inbox, it should find the row
- If it works, you'll see green checkmarks

---

## Step 5: Add OpenAI Reply Generator

1. Click the **circle** on the right of your Google Sheets module
2. Click **"Add another module"**
3. Search for: **"OpenAI"**
4. Select: **"OpenAI"** → **"Create a Chat Completion"**
5. **Connect your OpenAI account** (if not already connected)
   - Click "Add" next to Connection
   - Enter your OpenAI API key
   - Click "Save"
6. **Configure the module:**

   **Model:**
   - Select: **"gpt-4o-mini"** (cheapest) or **"gpt-3.5-turbo"**

   **Messages:**
   - Click **"Add item"**

   **Message 1 (System Message):**
   - **Role:** Select **"System"**
   - **Text Content:** Copy and paste this EXACTLY:
   
   ```
   You are an expert AI receptionist for a business automation service.

   You are continuing an email conversation with a potential client who has already received an initial email about our AI receptionist system.

   Your goals:
   - Be helpful, friendly, and professional
   - Answer their questions directly
   - Move them toward booking/activation if appropriate
   - Never say you are an AI
   - Never ask them to call you
   - Keep responses under 150 words
   - If they show buying intent, provide the activation link
   - If they ask about pricing, give simple pricing tiers (£79/£149/£299)
   - If they're confused, explain simply
   - If they're not interested, politely close the conversation

   You have access to their original enquiry details for context.
   ```

   - Click **"Add item"** again

   **Message 2 (User Message):**
   - **Role:** Select **"User"**
   - **Text Content:** Copy and paste this, then map the variables:
   
   ```
   Customer's reply:
   {{Gmail → Body Text}}

   Original enquiry details:
   Name: {{Google Sheets → Name}}
   Business: {{Google Sheets → Business Name}}
   Industry: {{Google Sheets → Industry}}
   Problem: {{Google Sheets → Problem}}
   Budget: {{Google Sheets → Budget}}

   Activation Link: https://buy.stripe.com/YOUR_LINK_HERE

   Write an appropriate response to their reply.
   ```

   **Now map the variables:**
   - Click on **{{Gmail → Body Text}}** → Delete it → Click the mapping icon → Select **Gmail → Body Text**
   - Click on **{{Google Sheets → Name}}** → Delete it → Click mapping icon → Select **Google Sheets → Name**
   - Click on **{{Google Sheets → Business Name}}** → Delete it → Click mapping icon → Select **Google Sheets → Business Name**
   - Click on **{{Google Sheets → Industry}}** → Delete it → Click mapping icon → Select **Google Sheets → Industry**
   - Click on **{{Google Sheets → Problem}}** → Delete it → Click mapping icon → Select **Google Sheets → Problem**
   - Click on **{{Google Sheets → Budget}}** → Delete it → Click mapping icon → Select **Google Sheets → Budget**
   - Replace **"https://buy.stripe.com/YOUR_LINK_HERE"** with your actual activation link (or leave it for now if you don't have one yet)

7. Click **"OK"**

**What this does:** Generates an intelligent reply based on what the customer said.

**Important:** If you can't see the Google Sheets fields when mapping, you need to run the scenario once first so Make.com knows what data is available.

---

## Step 6: Add Gmail Send Reply

1. Click the **circle** on the right of your OpenAI module
2. Click **"Add another module"**
3. Search for: **"Gmail"**
4. Select: **"Gmail"** → **"Send an Email"**
5. **Configure the module:**
   - **To:** Click mapping icon → Select **{{Gmail → From Email}}**
   - **Subject:** Type: **"Re: "** then click mapping icon → Select **{{Gmail → Subject}}**
   - **Body:** Click mapping icon → Navigate to **OpenAI → Choices → 1 → Message → Content**
     - (If you don't see this, run the scenario once first, then come back)
   - **From Name:** Type: **"AI Receptionist Team"**
   - Leave everything else as default
6. Click **"OK"**

**What this does:** Sends the AI-generated reply back to the customer.

---

## Step 7: Add Google Sheets Update

1. Click the **circle** on the right of your Gmail module
2. Click **"Add another module"**
3. Search for: **"Google Sheets"**
4. Select: **"Google Sheets"** → **"Update a Row"**
5. **Configure the module:**
   - **Spreadsheet:** Select **"AI Receptionist Leads"**
   - **Sheet:** Same sheet as before
   - **Row:** Click mapping icon → Select **{{Google Sheets → Row ID}}** (from the "Get a Row" module)
   - **Update these columns:**
     - **Status:** Type: **"In conversation"**
     - **Last Reply:** Click mapping icon → Select **{{Gmail → Date}}**
     - (If you have a "Reply Count" column, you can add 1 to it, but this is optional)
6. Click **"OK"**

**What this does:** Tracks that a conversation is happening and when the last reply was.

---

## Step 8: Test the Complete Flow

### Test Setup:

1. **Make sure your original scenario is running:**
   - Go to your first scenario (the one that sends initial emails)
   - Make sure it's **ON** (green switch at bottom)
   - Set scheduling to **"Every 15 minutes"**

2. **Activate this new scenario:**
   - Turn the switch at the bottom to **ON**
   - Set scheduling to **"Every 15 minutes"**

### Run the Test:

1. **Submit your Typeform** with a test email (use a real email you can check)
2. **Wait 15 minutes** (or trigger manually by clicking "Run once" on your first scenario)
3. **Check your email** - You should receive the initial AI email
4. **Reply to that email** with a question like: **"How much does this cost?"**
5. **Wait 15 minutes** (or trigger manually by clicking "Run once" on this reply handler scenario)
6. **Check your email again** - You should receive an AI-generated reply!

### What to Look For:

✅ Gmail module turns green (found the reply)  
✅ Filter module turns green (passed safety checks)  
✅ Google Sheets module turns green (found the lead)  
✅ OpenAI module turns green (generated reply)  
✅ Gmail Send module turns green (sent email)  
✅ Google Sheets Update module turns green (updated status)  

### If Something Fails:

- Click on the red module to see the error
- Check the execution log for details
- Common issues:
  - **Can't find lead in Google Sheets:** Make sure the email matches exactly
  - **OpenAI error:** Check your API key and credits
  - **Gmail error:** Check your Gmail connection

---

## Step 9: Add Error Handling (Optional but Recommended)

1. Click the **three dots** on any module
2. Select **"Add error handler"**
3. **Add a Gmail module:**
   - **To:** Your email address
   - **Subject:** "AI Receptionist Error Alert"
   - **Body:** "An error occurred in the reply handler. Check Make.com for details."
4. This will email you if something breaks

---

## ✅ Completion Checklist

- [ ] Scenario created and named "AI Receptionist - Reply Handler"
- [ ] Gmail Watch module configured
- [ ] Safety Filter added
- [ ] Google Sheets lookup working
- [ ] OpenAI reply generator configured
- [ ] Gmail send reply configured
- [ ] Google Sheets update configured
- [ ] Tested end-to-end successfully
- [ ] Scenario activated and scheduled

---

## 🎯 What You've Built

Your system now:
- ✅ Detects when someone replies to your AI emails
- ✅ Looks up who they are (from original enquiry)
- ✅ Generates an intelligent, contextual reply
- ✅ Sends the reply automatically
- ✅ Tracks the conversation in Google Sheets

**This is a complete automated conversation system!** 🎉

---

## 🆘 Troubleshooting

### "Can't find Google Sheets fields"
**Fix:** Run the scenario once first, then the fields will appear for mapping.

### "OpenAI says invalid API key"
**Fix:** Check your OpenAI API key in Make.com connections. Make sure you have credits.

### "Gmail not sending"
**Fix:** Reconnect your Gmail account. Check the "To" field is mapped correctly.

### "Subject doesn't contain 'Re:'"
**Fix:** Some email clients format replies differently. Try changing the filter to just check the "From" field instead.

### "Infinite loop (sending replies to yourself)"
**Fix:** Make sure your Filter module excludes your own email address.

---

## 📝 Next Steps

Once this is working:
1. ✅ Phase 1 Complete!
2. Move to **Phase 2:** Set up payment/activation links
3. Then **Phase 5:** Final testing
4. Then **Phase 6:** Go live!

**You're building something amazing!** 💪
