# Google Sheets Alternatives - If "Get a Row" Not Available

If you don't see "Get a Row", here are alternatives:

---

## Option 1: Use "Search Rows" or "List Rows"

Some Make.com plans show different names:

**Look for:**
- **"Search Rows"** ← This is the same as "Get a Row"
- **"List Rows"** ← Can work, but you'll need to filter
- **"Get Rows"** (plural) ← Similar function

---

## Option 2: Use "Watch Rows" (Different Approach)

If you can't find "Get a Row", you can use a different method:

### Instead of "Get a Row", use this flow:

1. **Module 2: Google Sheets → Watch Rows**
   - This watches your sheet for new rows
   - But we need to match by email...

### Better Alternative: Store Email in Gmail Filter

Actually, a simpler approach - let's modify the flow:

**Instead of looking up the lead, we can:**
1. Store the lead's email in the Gmail subject or use a different approach
2. Or use "List Rows" and filter

---

## Option 3: Use "List Rows" with Filter

1. Select: **"Google Sheets"** → **"List Rows"**
2. **Spreadsheet:** Select `AI Receptionist Leads`
3. **Sheet:** Select your sheet
4. **Filter:**
   - Column: `Email`
   - Operator: `Equal`
   - Value: Map from `Gmail → From Email`
5. **Limit:** Set to `1` (we only want one row)

This will give you the row that matches the email.

---

## Option 4: Skip the Lookup Entirely (Simplest!)

**Actually, you might not need to look up the lead at all!**

You can modify the OpenAI prompt to work without the original lead data:

### Simplified Flow:

```
Gmail Watch → OpenAI (with just the reply) → Gmail Send → Google Sheets Update
```

The AI can still generate a good reply even without the original lead context.

---

## What Options Do You See?

When you search "Google Sheets", what exact options appear?

Please tell me which of these you see:
- [ ] Watch Rows
- [ ] List Rows
- [ ] Add a Row
- [ ] Update a Row
- [ ] Search Rows
- [ ] Get Rows
- [ ] Something else?

Once I know what you see, I can give you the exact steps!

---

## Quick Fix: Use "List Rows"

**Most likely, you have "List Rows" - use this:**

1. Select: **"Google Sheets"** → **"List Rows"**
2. **Spreadsheet:** `AI Receptionist Leads`
3. **Sheet:** Your sheet tab
4. **Filter:** 
   - Click "Set up a filter"
   - Column: `Email`
   - Operator: `Equal`
   - Value: Map from `Gmail → From Email`
5. **Limit:** `1`
6. Click **OK**

This will return the row that matches the email address.

Then in your OpenAI module, you'll access the data as:
- `{{Google Sheets → Rows[1].Name}}` (instead of `{{Google Sheets → Name}}`)
- `{{Google Sheets → Rows[1].Business Name}}`
- etc.

Let me know what you see and I'll give you the exact configuration!
