# Super Simple Setup - Skip Router, Just Build It

Let's skip the Router entirely and build the core functionality first. You can add safety checks later.

---

## Your Simple Flow (5 Modules)

```
[Gmail Watch] 
    ↓
[Google Sheets Lookup]
    ↓
[OpenAI Generate Reply]
    ↓
[Gmail Send Reply]
    ↓
[Google Sheets Update]
```

**No Router needed!** Just 5 modules in a row.

---

## MODULE 1: Gmail → Watch Emails

1. Click **"+"** button
2. Search: **"Gmail"**
3. Select: **"Gmail"** → **"Watch Emails"**
4. Connect your Gmail
5. **Filter:**
   - Subject contains: `Re:`
   - From does not equal: `[YOUR EMAIL]`
6. Click **OK**

---

## MODULE 2: Google Sheets → Get a Row

1. Click the **circle** on the right of Gmail module
2. Click **"Add another module"**
3. Search: **"Google Sheets"**
4. Select: **"Google Sheets"** → **"Get a Row"**
5. Connect Google account
6. **Spreadsheet:** Select `AI Receptionist Leads`
7. **Sheet:** Select the sheet tab
8. **Search:**
   - Column: `Email`
   - Search Value: Click mapping → Select `Gmail → From Email`
9. Click **OK**

---

## MODULE 3: OpenAI → Create Chat Completion

1. Click the **circle** on the right of Google Sheets module
2. Click **"Add another module"**
3. Search: **"OpenAI"**
4. Select: **"OpenAI"** → **"Create a Chat Completion"**
5. Connect OpenAI (enter your API key)
6. **Model:** `gpt-4o-mini`
7. **Messages:**
   - Click **"Add item"**
   - **Message 1:**
     - Role: `System`
     - Text Content: Copy this:

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
```

   - Click **"Add item"** again
   - **Message 2:**
     - Role: `User`
     - Text Content: Copy this, then map the variables:

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
   - Click on `{{Gmail → Body Text}}` → Delete it → Click mapping icon → Select `Gmail → Body Text`
   - Click on `{{Google Sheets → Name}}` → Delete it → Click mapping icon → Select `Google Sheets → Name`
   - Do the same for Business Name, Industry, Problem, Budget
   - Replace the activation link with your real one (or leave placeholder)

8. Click **OK**

---

## MODULE 4: Gmail → Send an Email

1. Click the **circle** on the right of OpenAI module
2. Click **"Add another module"**
3. Search: **"Gmail"**
4. Select: **"Gmail"** → **"Send an Email"**
5. **To:** Click mapping → Select `Gmail → From Email`
6. **Subject:** Type `Re: ` then click mapping → Select `Gmail → Subject`
7. **Body:** Click mapping → Navigate to `OpenAI → Choices → 1 → Message → Content`
   - (If you don't see this, run the scenario once first, then come back)
8. **From Name:** Type `AI Receptionist Team`
9. Click **OK**

---

## MODULE 5: Google Sheets → Update a Row

1. Click the **circle** on the right of Gmail module
2. Click **"Add another module"**
3. Search: **"Google Sheets"**
4. Select: **"Google Sheets"** → **"Update a Row"**
5. **Spreadsheet:** Select `AI Receptionist Leads`
6. **Sheet:** Same as Module 2
7. **Row:** Click mapping → Select `Google Sheets → Row ID` (from Module 2)
8. **Update:**
   - **Status:** Type `In conversation`
   - **Last Reply:** Click mapping → Select `Gmail → Date`
9. Click **OK**

---

## Test It

1. **Save your scenario**
2. **Turn it ON** (switch at bottom)
3. **Set scheduling:** Every 15 minutes
4. **Test:**
   - Submit your Typeform
   - Wait for initial AI email
   - Reply to that email
   - Wait 15 minutes
   - Check if you got an AI reply!

---

## That's It!

You now have a working reply automation. No Router needed.

**Later, if you want to add safety checks:**
- You can add Router between Gmail and Google Sheets
- But it's not required - your system works without it!

**You're done!** 🎉
