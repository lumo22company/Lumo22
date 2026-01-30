# Simple Reply Automation - 3 Modules Only

This is the simplified version. Much easier to set up and test!

---

## Your Flow (3 Modules)

```
[Gmail Watch] 
    ↓
[OpenAI Generate Reply]
    ↓
[Gmail Send Reply]
```

**That's it!** Plus one simple filter.

---

## STEP 1: Gmail → Watch Emails

1. Create a new scenario: **"AI Receptionist - Reply Handler"**
2. Click **"+"** button
3. Search: **"Gmail"**
4. Select: **"Gmail"** → **"Watch Emails"**
5. Connect your Gmail account
6. **Configure:**
   - **Criteria:** `Unread messages`
   - **Folder:** `Inbox`
7. Click **OK**

---

## STEP 2: Add OpenAI Module

1. Click the **circle** on the right of Gmail module
2. Click **"Add another module"**
3. Search: **"OpenAI"**
4. Select: **"OpenAI"** → **"Create a Chat Completion"**
5. Connect your OpenAI account (enter API key)
6. **Don't configure yet** - we'll do that in Step 4

You should now see a line connecting Gmail to OpenAI.

---

## STEP 3: Add Simple Filter

1. **Hover over the line** between Gmail and OpenAI
2. You'll see a **funnel icon** - click it
3. **Filter name:** `Ignore my own emails`
4. **Condition:**
   - **Left:** Click mapping → Select `Gmail → From Email` (NOT "From Name" - use the email address field)
   - **Operator:** `Text operators` → `does not contain`
   - **Right:** Type your email address (the one you send AI emails from)
5. Click **OK**

**Important:** Use **"From Email"** (the email address), NOT "From Name" (the display name). You want to filter by the actual email address.

**That's it!** This prevents replying to your own emails.

---

## STEP 4: Configure OpenAI

1. Click on your **OpenAI module**
2. **Model:** Select `gpt-4o-mini` (or `gpt-3.5-turbo`)
3. **Messages:** (This section is required - you must add at least one message)

   **Click "Add item" or the "+" button to add your first message**

   **Message 1 (System Message):**
   - **Role:** Select `System` from the dropdown
   - **Text Content:** Click in the text box and paste this exactly:

```
You are an AI receptionist continuing an email conversation.
Be helpful and professional.
Never say you are an AI.
Never ask for a phone call.
Guide them to activation if appropriate.
```

   **Click "Add item" or "+" again to add a second message**

   **Message 2 (User Message):**
   - **Role:** Select `User` from the dropdown
   - **Text Content:** 
     - Click in the text box
     - Click the **mapping icon** (looks like `</>` or `{}` or a chain link)
     - Navigate to: `Gmail → Body Text`
     - Click to select it
     - This will insert `{{Gmail → Body Text}}` or similar

4. **Click "OK" or "Save"** to save the module

**If you see other fields like "Image Input Type" or "Image Detail" - just leave them empty/blank.**

---

## STEP 5: Add Gmail Send

1. Click the **circle** on the right of OpenAI module
2. Click **"Add another module"**
3. Search: **"Gmail"**
4. Select: **"Gmail"** → **"Send an Email"**
5. **Configure:**
   - **To:** Click mapping → Select `Gmail → From Email`
   - **Subject:** Just click mapping → Select `Gmail → Subject` directly (don't type "Re:" - the original subject already has it, and Gmail handles threading automatically)
   - **Body Type:** (if you see this field) Select **`Raw HTML`** or **`HTML`** or **`Plain text`** - any of these work fine
   - **Body:** Click mapping → Navigate to `OpenAI → Result` or `OpenAI → Choices → 1 → Message → Content`
     - (If you don't see this, run the scenario once first, then come back)
   - **From Name:** (optional - if you see this field) Type `AI Receptionist Team`
     - If you don't see this field, that's fine - just skip it. The email will still send.
   - **Map toggles/Parse options:** (if you see any) Leave them OFF/default - you don't need them for this simple automation
6. Click **OK**

**Note:** If you see any toggle switches for "Parse email", "Map attachments", or similar options, leave them OFF. You don't need them for this automation.

**Note:** If you see "Body Type" field, choose **HTML** (preferred) or **Plain text**. Both will work - HTML just allows for better formatting if needed.

---

## Test It!

1. **Save your scenario**
2. **Turn it ON** (switch at bottom)
3. **Set scheduling:** Every 15 minutes (free plan) or 1-5 minutes (paid)
4. **Test:**
   - Submit your Typeform
   - Wait for initial AI email (from your first scenario)
   - Reply to that email with: "How much does this cost?"
   - Wait 15 minutes (or trigger manually)
   - Check if you got an AI reply!

---

## What You've Built

✅ Watches for email replies  
✅ Filters out your own emails  
✅ AI generates a reply  
✅ Sends the reply automatically  

**That's a complete automated conversation system!**

---

## Optional: Add Context Later

If you want the AI to know who the person is (their name, business, etc.), you can add Google Sheets lookup later. But this simple version works great for testing and getting started!

---

## Troubleshooting

**"Can't see OpenAI output in Gmail module"**
- Run the scenario once first (click "Run once")
- Then the OpenAI fields will appear for mapping

**"Getting replies to my own emails"**
- Check the filter condition
- Make sure "does not contain" has your exact email address

**"AI replies are generic"**
- The AI only sees the reply text, not the original lead data
- This is fine for testing - you can add Google Sheets lookup later for more context

---

## Next Steps

Once this works:
1. ✅ Test it with a few replies
2. ✅ See how the AI responds
3. ✅ If you want more personalized replies, add Google Sheets lookup later
4. ✅ Move to Phase 2: Set up payment/activation links

**You're done!** This is much simpler and works perfectly. 🎉
