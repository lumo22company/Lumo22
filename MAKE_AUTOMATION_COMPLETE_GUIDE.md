# Complete Make.com AI Receptionist Automation Guide

This guide completes your AI-powered lead generation and appointment setting automation built in Make.com.

## 🎯 What You've Built So Far

✅ **Typeform** - Lead capture form  
✅ **Google Sheets** - Lead database  
✅ **Make.com** - Automation platform  
✅ **OpenAI** - AI email generation  
✅ **Gmail** - Automated email sending  

## 📋 Current System Flow

```
Lead fills Typeform
    ↓
Data saved to Google Sheets
    ↓
Make.com triggers (every 15 mins on free plan)
    ↓
OpenAI generates personalized email
    ↓
Gmail sends email with booking link
    ↓
Google Sheets updated with status
```

---

## 🚀 Step 1: Add Automated Reply Handling

This is the missing piece - when customers reply to your AI emails, the system will automatically respond.

### Setup in Make.com

**Create a NEW scenario** called: "AI Receptionist - Reply Handler"

#### Module 1: Gmail Watch for Emails

1. **Trigger:** Gmail → Watch Emails
2. **Connection:** Connect your Gmail account
3. **Filter:**
   - **Subject contains:** "Re:" OR "Re: Your enquiry"
   - **From:** (not your own email)
   - **Label:** (optional - you can create a label like "AI-Replies" and filter by that)

**Why:** This watches for replies to your automated emails.

#### Module 2: Filter (Safety Check)

1. **Module:** Flow Control → Filter
2. **Condition:** 
   - Email body does NOT contain: "unsubscribe" OR "opt out"
   - Email from is NOT in your blocklist
   - Email is NOT from your own address

**Why:** Prevents infinite loops and spam.

#### Module 3: Get Original Lead Data

1. **Module:** Google Sheets → Get a Row
2. **Spreadsheet:** AI Receptionist Leads
3. **Search:** Find row where Email = {{Gmail → From Email}}
4. **Get:** Name, Business Name, Industry, Booking Link, Status

**Why:** The AI needs context about who this person is.

#### Module 4: OpenAI Generate Reply

1. **Module:** OpenAI → Create a Chat Completion
2. **Model:** gpt-4o-mini (or gpt-3.5-turbo for cheaper)
3. **Messages:**

**System Message:**
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
- If they ask about pricing, give simple pricing tiers
- If they're confused, explain simply
- If they're not interested, politely close the conversation

You have access to their original enquiry details for context.
```

**User Message:**
```
Customer's reply:
{{Gmail → Body Text}}

Original enquiry details:
Name: {{Google Sheets → Name}}
Business: {{Google Sheets → Business Name}}
Industry: {{Google Sheets → Industry}}
Problem: {{Google Sheets → Problem}}
Budget: {{Google Sheets → Budget}}

Booking/Activation Link: {{Google Sheets → Booking Link}}

Write an appropriate response to their reply.
```

#### Module 5: Send Reply Email

1. **Module:** Gmail → Send an Email
2. **To:** {{Gmail → From Email}}
3. **Subject:** Re: {{Gmail → Subject}}
4. **Body:** {{OpenAI → Choices → Message → Content}}
5. **From Name:** AI Receptionist Team

#### Module 6: Update Google Sheets

1. **Module:** Google Sheets → Update a Row
2. **Spreadsheet:** AI Receptionist Leads
3. **Row:** The row you found in Module 3
4. **Update:**
   - **Last Reply:** {{Gmail → Date}}
   - **Reply Count:** (increment by 1)
   - **Status:** "In conversation"

**Why:** Track conversation history.

### Test the Reply System

1. Submit your Typeform with a test email
2. Wait for the initial AI email to arrive
3. Reply to that email with a question like: "How much does this cost?"
4. Watch Make.com process the reply
5. You should receive an AI-generated response within 15 minutes

---

## 💰 Step 2: Activation & Payment Flow

Your system needs a way for clients to activate and pay without any calls.

### Option A: Stripe Payment Links (Recommended)

1. **Create Stripe Account:** https://stripe.com
2. **Create Products:**
   - Starter Plan: £79/month (recurring)
   - Standard Plan: £149/month (recurring)
   - Premium Plan: £299/month (recurring)
3. **Get Payment Links:**
   - Copy the payment link for each tier
   - These will be used in your AI emails

### Option B: Gumroad (Simpler)

1. **Create Gumroad Account:** https://gumroad.com
2. **Create Products:**
   - Set up as subscriptions
   - Use the product links in your AI emails

### Update Your AI Email Prompt

In your **original Make.com scenario** (the one that sends initial emails), update the OpenAI prompt ending:

```
End the email with:

"You've just interacted with our AI receptionist system. This is exactly how your customers would experience it.

Activate your AI receptionist here:
[YOUR ACTIVATION LINK]

No calls needed. No setup calls. Just activate and go live."
```

Replace `[YOUR ACTIVATION LINK]` with your Stripe/Gumroad payment link.

---

## 📝 Step 3: Client Onboarding Automation

After payment, clients need to provide their details.

### Create Onboarding Form

**In Typeform, create a new form:** "Client Onboarding"

**Questions:**
1. **Email** (from payment)
2. **Business Name**
3. **Business Email** (where they want notifications)
4. **Booking Link** (Calendly, Fresha, etc.)
5. **Industry**
6. **Logo** (optional file upload)

### Connect to Google Sheets

1. **Typeform → Google Sheets**
2. **Create new sheet:** "Active Clients"
3. **Columns:**
   - Timestamp
   - Email
   - Business Name
   - Business Email
   - Booking Link
   - Industry
   - Plan Type
   - Status
   - Activation Date

### Create Make.com Onboarding Scenario

**Scenario:** "Client Activation"

1. **Trigger:** Google Sheets → Watch Rows (Active Clients sheet)
2. **Action:** Google Sheets → Update Row (AI Receptionist Leads)
   - Match by email
   - Update Booking Link with client's link
   - Update Status to "Active"
3. **Action:** Gmail → Send Email
   - **To:** Client's business email
   - **Subject:** Your AI Receptionist is Now Live
   - **Body:** 
   ```
   Hi {{Business Name}},
   
   Your AI receptionist is now active!
   
   Your form link: [YOUR TYPEFORM LINK]
   
   Every enquiry will now:
   - Get an instant AI response
   - Be sent to your booking link
   - Be tracked in your dashboard
   
   Questions? Just reply to this email.
   
   Best,
   Sophie
   ```

---

## 🎨 Step 4: Update Your Typeform End Screen

Go back to your original Typeform and update the end screen message:

**Current:**
```
Thanks! If it looks like we can help, you'll receive an email shortly with next steps.
```

**Updated:**
```
Thanks! Our AI system is reviewing your enquiry and you'll receive a response within the next 15 minutes.
```

This sets proper expectations.

---

## 📊 Step 5: Create Client Dashboard (Optional but Recommended)

Create a simple Google Sheet that clients can view:

**Sheet Name:** "Client Dashboard - [Business Name]"

**Columns:**
- Date
- Lead Name
- Email
- Phone
- Service
- AI Response Sent
- Booking Status
- Revenue (if applicable)

**Share this sheet** with clients so they can see their leads in real-time.

---

## 🔄 Complete System Architecture

```
┌─────────────────┐
│   Typeform      │ ← Lead fills form
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Google Sheets  │ ← Stores lead data
│  (Leads DB)     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Make.com      │
│  Scenario 1:    │
│  Initial Email  │
└────────┬────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐  ┌────────┐
│ OpenAI │  │ Gmail  │ ← Sends AI email
└────────┘  └────┬───┘
                 │
                 ↓
         ┌───────────────┐
         │ Customer      │
         │ Receives Email│
         └───────┬───────┘
                 │
         ┌───────┴───────┐
         │               │
    ┌────▼────┐    ┌────▼────┐
    │ Books   │    │ Replies │
    │ Call    │    │ to Email│
    └─────────┘    └────┬────┘
                        │
                        ↓
              ┌─────────────────┐
              │  Make.com       │
              │  Scenario 2:    │
              │  Reply Handler  │
              └────────┬────────┘
                       │
                  ┌────┴────┐
                  ↓         ↓
            ┌────────┐  ┌────────┐
            │ OpenAI │  │ Gmail  │ ← Sends AI reply
            └────────┘  └────────┘
```

---

## ✅ Testing Checklist

Before going live, test:

- [ ] Typeform submission creates row in Google Sheets
- [ ] Make.com triggers within 15 minutes
- [ ] OpenAI generates appropriate email
- [ ] Gmail sends email successfully
- [ ] Email contains booking/activation link
- [ ] Google Sheets updates with "Email sent" status
- [ ] Reply to email triggers reply handler
- [ ] AI generates appropriate reply
- [ ] Reply email is sent back
- [ ] Google Sheets tracks conversation

---

## 🚀 Going Live

1. **Turn on Make.com scenarios:**
   - Set scheduling to "Every 15 minutes" (or 1-5 mins on paid plan)
   - Activate both scenarios

2. **Test with real submission:**
   - Use a friend's email
   - Submit your Typeform
   - Wait for email
   - Reply to test the reply system

3. **Share your Typeform:**
   - Add to your website
   - Share on social media
   - Use in outreach

---

## 💡 Pro Tips

1. **Monitor Make.com execution logs** - Check for errors daily
2. **Review AI responses weekly** - Tweak prompts if needed
3. **Track conversion rates** - How many leads → bookings?
4. **A/B test email prompts** - Try different tones/styles
5. **Set up alerts** - Get notified if automation fails

---

## 🆘 Troubleshooting

**Emails not sending:**
- Check Gmail connection in Make.com
- Verify email module is mapped correctly
- Check Make.com execution logs

**AI responses are generic:**
- Add more context to your OpenAI prompt
- Include more lead details in the prompt
- Test with different model (gpt-4o-mini vs gpt-4)

**Replies not triggering:**
- Check Gmail filter settings
- Verify "Watch Emails" is connected
- Make sure subject contains "Re:"

**Google Sheets not updating:**
- Check sheet permissions
- Verify column names match exactly
- Test the connection in Make.com

---

## 📈 Next Steps

1. ✅ Complete reply handling setup
2. ✅ Set up payment/activation links
3. ✅ Create onboarding automation
4. ✅ Test everything end-to-end
5. ✅ Start outreach to first 20 businesses
6. ✅ Get first paying client
7. ✅ Iterate based on feedback

You now have a fully automated AI receptionist business! 🎉
