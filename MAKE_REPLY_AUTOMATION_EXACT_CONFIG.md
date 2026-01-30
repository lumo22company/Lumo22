# Make.com Reply Automation - Exact Configuration

Copy and paste these exact settings into your Make.com scenario.

---

## Scenario Name
**"AI Receptionist - Reply Handler"**

---

## MODULE 1: Gmail → Watch Emails

### Connection
- Connect your Gmail account (if not already connected)

### Configuration
- **Mailbox:** Select your Gmail account
- **Filter:** Set up a filter
  - **Condition 1:**
    - Field: `Subject`
    - Operator: `Contains`
    - Value: `Re:`
  - **Condition 2:** (Add another condition)
    - Field: `From`
    - Operator: `Does not equal`
    - Value: `[YOUR EMAIL ADDRESS]` (the one sending AI emails)
- **Label:** (leave empty)

**Click OK**

---

## MODULE 2: Flow Control → Router (OPTIONAL - Can Skip!)

### ⚠️ IMPORTANT: You Can Skip This Entirely!

**The Router is just a safety feature. Your system will work fine without it.**

**If Router is confusing, just skip to Module 3 (Google Sheets) and come back to this later.**

---

### If You Want to Add Router (Optional Safety Check):

**Step 1: Add Router Module**
1. Click the **"+"** button after your Gmail module
2. Search for: **"router"**
3. Click on **"Router"** (under Flow control category)

**Step 2: Router Will Show Two Routes**
- You'll see: **Route 1** and **Route 2**
- That's normal - Router always has at least 2 routes

**Step 3: Set Up Route 1 (This is where good emails go)**
1. Click on **"Route 1"** (or it might say "Click to set up")
2. You'll see a button like **"Add condition"** or **"Set up filter"** - click it
3. Add this ONE condition (start simple):
   - **Field:** Click mapping icon → Select `Gmail → From Email`
   - **Operator:** Select `Does not equal`
   - **Value:** Type your email address (the one you send AI emails from)
4. Click **OK** or **Save** on Route 1

**Step 4: Leave Route 2 Empty**
- Don't click on Route 2
- Don't add anything to Route 2
- Just ignore it completely

**Step 5: Connect Next Module to Route 1**
- When you add Module 3 (Google Sheets), make sure you connect it to **Route 1**
- Click the circle on the right of **Route 1** (not Route 2)
- Then add your Google Sheets module

**That's it!** This prevents replying to your own emails.

---

### Alternative: Skip Router Entirely

**If Router is too confusing, just:**
1. Skip this module
2. Go straight to Module 3 (Google Sheets)
3. Connect Google Sheets directly to Gmail Watch
4. Test your system
5. Add Router later if needed

**Your automation will work fine without Router - it's just a safety feature.**

---

## MODULE 3: Google Sheets → Get a Row

### Connection
- Connect your Google account (if not already connected)

### Configuration
- **Spreadsheet:** `AI Receptionist Leads` (select from dropdown)
- **Sheet:** Select the sheet tab (usually "Sheet1" or the one Typeform created)
- **Search:** Set up a search
  - **Column:** `Email` (or whatever column has email addresses)
  - **Search Value:** Click mapping icon → Select `{{1.From Email}}`

**Click OK**

---

## MODULE 4: OpenAI → Create a Chat Completion

### Connection
- Connect your OpenAI account
- Enter your API key

### Configuration

**Model:**
- Select: `gpt-4o-mini` (or `gpt-3.5-turbo` for cheaper)

**Messages:**

Click **"Add item"**

**Message 1:**
- **Role:** `System`
- **Text Content:** Copy this EXACTLY:

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

Click **"Add item"** again

**Message 2:**
- **Role:** `User`
- **Text Content:** Copy this, then map the variables (see below):

```
Customer's reply:
{{1.Body Text}}

Original enquiry details:
Name: {{3.Name}}
Business: {{3.Business Name}}
Industry: {{3.Industry}}
Problem: {{3.Problem}}
Budget: {{3.Budget}}

Activation Link: https://buy.stripe.com/YOUR_LINK_HERE

Write an appropriate response to their reply.
```

### Mapping the Variables:

**IMPORTANT:** After pasting the text above, you need to replace the `{{}}` placeholders with actual mapped fields:

1. **{{1.Body Text}}** → Click on it → Delete → Click mapping icon → Select `Gmail → Body Text`
2. **{{3.Name}}** → Click on it → Delete → Click mapping icon → Select `Google Sheets → Name`
3. **{{3.Business Name}}** → Click on it → Delete → Click mapping icon → Select `Google Sheets → Business Name`
4. **{{3.Industry}}** → Click on it → Delete → Click mapping icon → Select `Google Sheets → Industry`
5. **{{3.Problem}}** → Click on it → Delete → Click mapping icon → Select `Google Sheets → Problem`
6. **{{3.Budget}}** → Click on it → Delete → Click mapping icon → Select `Google Sheets → Budget`
7. **Replace `https://buy.stripe.com/YOUR_LINK_HERE`** with your actual Stripe activation link (or leave as placeholder if you don't have it yet)

**Note:** The numbers (1, 3) refer to module numbers. Adjust if your modules are numbered differently.

**Click OK**

---

## MODULE 5: Gmail → Send an Email

### Configuration
- **To:** Click mapping icon → Select `{{1.From Email}}`
- **Subject:** Type `Re: ` then click mapping icon → Select `{{1.Subject}}`
- **Body:** Click mapping icon → Navigate to:
  - `OpenAI → Choices → 1 → Message → Content`
  - (If you don't see this path, run the scenario once first, then come back)
- **From Name:** Type `AI Receptionist Team`
- **From:** (leave as default - your connected Gmail)

**Click OK**

---

## MODULE 6: Google Sheets → Update a Row

### Configuration
- **Spreadsheet:** `AI Receptionist Leads` (select from dropdown)
- **Sheet:** Same sheet as Module 3
- **Row:** Click mapping icon → Select `{{3.Row ID}}` (from the Get a Row module)
- **Update these columns:**
  - **Status:** Type `In conversation`
  - **Last Reply:** Click mapping icon → Select `{{1.Date}}` (from Gmail module)
  - (If you have a "Reply Count" column, you can add logic to increment it, but this is optional)

**Click OK**

---

## Testing Instructions

1. **Save your scenario** (click Save at top)

2. **Run it once manually:**
   - Click "Run once" at the bottom
   - This will test the modules (you may see some errors if there's no email to process, that's OK)

3. **Test the full flow:**
   - Submit your Typeform with a test email
   - Wait for initial AI email (from your first scenario)
   - Reply to that email with: "How much does this cost?"
   - Wait 15 minutes (or trigger manually)
   - Check if you received an AI reply

4. **Activate the scenario:**
   - Turn the switch at bottom to **ON**
   - Set scheduling to **"Every 15 minutes"** (free plan) or **"Every 1-5 minutes"** (paid plan)

---

## Field Mapping Reference

### From Gmail Watch (Module 1):
- `{{1.From Email}}` → Customer's email address
- `{{1.Subject}}` → Email subject
- `{{1.Body Text}}` → Customer's reply text
- `{{1.Date}}` → When they replied

### From Google Sheets (Module 3):
- `{{3.Name}}` → Lead's name
- `{{3.Business Name}}` → Their business name
- `{{3.Industry}}` → Their industry
- `{{3.Problem}}` → Their problem
- `{{3.Budget}}` → Their budget
- `{{3.Row ID}}` → Row identifier (for updating)

### From OpenAI (Module 4):
- `{{4.Choices[1].Message.Content}}` → The AI-generated reply text

---

## Troubleshooting

### "Can't see Google Sheets fields"
**Solution:** Run the scenario once first (even if it errors), then the fields will appear for mapping.

### "OpenAI says invalid API key"
**Solution:** 
- Go to Connections in Make.com
- Edit your OpenAI connection
- Verify your API key is correct
- Check you have credits in your OpenAI account

### "Gmail not sending"
**Solution:**
- Reconnect your Gmail account
- Check the "To" field is mapped to `{{1.From Email}}`
- Verify your Gmail account has permission to send emails

### "Can't find lead in Google Sheets"
**Solution:**
- Make sure the email in the reply matches exactly the email in your sheet
- Check the column name is "Email" (case-sensitive)
- Verify the spreadsheet name is correct

### "Infinite loop (sending to myself)"
**Solution:**
- Make sure Module 2 (Filter) excludes your email address
- Check Condition 3 in the Filter module

---

## Quick Copy-Paste Prompts

### System Message (for OpenAI Module):
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

### User Message Template (map the variables):
```
Customer's reply:
{{1.Body Text}}

Original enquiry details:
Name: {{3.Name}}
Business: {{3.Business Name}}
Industry: {{3.Industry}}
Problem: {{3.Problem}}
Budget: {{3.Budget}}

Activation Link: https://buy.stripe.com/YOUR_LINK_HERE

Write an appropriate response to their reply.
```

---

## Final Checklist

- [ ] All 6 modules added and configured
- [ ] Gmail account connected
- [ ] Google account connected
- [ ] OpenAI account connected with valid API key
- [ ] All variables mapped correctly
- [ ] Tested with "Run once"
- [ ] Scenario saved
- [ ] Scenario activated and scheduled
- [ ] Tested end-to-end (submit form → reply → receive AI response)

**You're done!** 🎉

---

## Next Steps

Once this is working:
1. ✅ Phase 1 Complete!
2. Move to **Phase 2:** Set up payment/activation links (see `COMPLETE_SETUP_ACTION_PLAN.md`)
3. Update your activation link in the OpenAI prompt above
4. Start getting clients!
