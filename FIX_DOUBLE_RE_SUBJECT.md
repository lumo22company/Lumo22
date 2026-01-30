# Fix: Double "Re: Re:" in Subject

## The Problem
Your reply emails show "Re: Re:" in the subject because:
- The original email already has "Re:" in the subject
- You're adding another "Re:" to it
- Result: "Re: Re: Your enquiry..."

## The Fix

### Option 1: Just Use Original Subject (Simplest)

1. Go to your **Gmail Send** module (Step 5)
2. Find the **Subject** field
3. **Remove** the `Re: ` text you typed
4. **Just map** `Gmail → Subject` directly
5. Click **OK**

**Result:** Subject will be "Re: Your enquiry..." (correct!)

---

### Option 2: Use Text Formatter (If You Want to Ensure "Re:")

If you want to make sure "Re:" is always there (even if original doesn't have it):

1. Add a **Text** module between OpenAI and Gmail Send
2. Use this formula:
   ```
   {{#if (startsWith(Gmail → Subject, "Re:"))}}
   {{Gmail → Subject}}
   {{else}}
   Re: {{Gmail → Subject}}
   {{/if}}
   ```
3. Map this output to the Subject field

**But honestly, Option 1 is simpler and works fine!**

---

## Quick Fix Steps

1. Open your scenario in Make.com
2. Click on the **Gmail Send** module (last module)
3. Find the **Subject** field
4. **Delete** the `Re: ` text
5. **Just map** `Gmail → Subject` (click mapping icon → select `Gmail → Subject`)
6. Save

**Done!** Your subjects will now be correct.

---

## Why This Works

- Gmail automatically handles email threading
- The original subject already has "Re:" if it's a reply
- You don't need to add it again
- Email clients will thread the conversation correctly

**That's it!** Simple fix. 🎉
