# Make.com Reply Automation - Visual Flow

## Complete Module Flow

```
┌─────────────────────────────────┐
│  MODULE 1: Gmail Watch Emails   │
│                                  │
│  Watches for replies to your    │
│  automated emails                │
│                                  │
│  Filter: Subject contains "Re:" │
│  Filter: From ≠ your email      │
└──────────────┬──────────────────┘
               │
               ↓ (triggers when email arrives)
               │
┌─────────────────────────────────┐
│  MODULE 2: Filter (Safety)      │
│                                  │
│  Prevents infinite loops         │
│                                  │
│  ✓ Body ≠ "unsubscribe"         │
│  ✓ Body ≠ "opt out"             │
│  ✓ From ≠ your email            │
└──────────────┬──────────────────┘
               │
               ↓ (only continues if passes)
               │
┌─────────────────────────────────┐
│  MODULE 3: Google Sheets        │
│  Get a Row                      │
│                                  │
│  Finds the original lead by:    │
│  Email = {{Gmail From Email}}   │
│                                  │
│  Returns:                       │
│  • Name                         │
│  • Business Name                │
│  • Industry                     │
│  • Problem                      │
│  • Budget                       │
│  • Row ID                       │
└──────────────┬──────────────────┘
               │
               ↓ (has context about who replied)
               │
┌─────────────────────────────────┐
│  MODULE 4: OpenAI               │
│  Create Chat Completion         │
│                                  │
│  System Message:                │
│  "You are an AI receptionist..." │
│                                  │
│  User Message:                   │
│  Customer's reply +             │
│  Original lead details           │
│                                  │
│  Output: AI-generated response  │
└──────────────┬──────────────────┘
               │
               ↓ (AI has written the reply)
               │
┌─────────────────────────────────┐
│  MODULE 5: Gmail Send Email     │
│                                  │
│  To: {{Gmail From Email}}       │
│  Subject: "Re: " + original     │
│  Body: {{OpenAI Content}}        │
│                                  │
│  Sends the AI reply             │
└──────────────┬──────────────────┘
               │
               ↓ (email sent)
               │
┌─────────────────────────────────┐
│  MODULE 6: Google Sheets        │
│  Update a Row                   │
│                                  │
│  Updates the lead row:          │
│  • Status = "In conversation"   │
│  • Last Reply = {{Gmail Date}}  │
│                                  │
│  Tracks conversation history     │
└─────────────────────────────────┘
```

---

## Data Flow

### Input (from Gmail):
```
Email arrives with:
- From: customer@example.com
- Subject: "Re: Your enquiry about our AI booking system"
- Body: "How much does this cost?"
- Date: 2026-01-27 14:30:00
```

### Processing:
```
1. Filter checks: ✓ Not unsubscribe, ✓ Not from me
2. Google Sheets finds: Lead #123 (Sophie, Aesthetics Clinic, etc.)
3. OpenAI receives:
   - Customer's question: "How much does this cost?"
   - Context: Sophie, Aesthetics, Budget £300-700
4. OpenAI generates: "Hi Sophie, our pricing starts at £79/month..."
```

### Output:
```
Email sent to customer@example.com:
- Subject: "Re: Your enquiry about our AI booking system"
- Body: "Hi Sophie, our pricing starts at £79/month..."

Google Sheets updated:
- Status: "In conversation"
- Last Reply: 2026-01-27 14:30:00
```

---

## Module Configuration Summary

| Module | Type | Key Settings |
|--------|------|--------------|
| 1. Gmail Watch | Trigger | Subject contains "Re:", From ≠ your email |
| 2. Filter | Flow Control | Exclude unsubscribe, opt-out, your email |
| 3. Google Sheets | Data | Search by email, get lead details |
| 4. OpenAI | AI | System + User messages, map all variables |
| 5. Gmail Send | Action | To: customer, Body: AI output |
| 6. Google Sheets | Data | Update status and timestamp |

---

## Field Mapping Quick Reference

### Module 1 → Module 2:
- `{{1.From Email}}` → Use in Filter condition
- `{{1.Body Text}}` → Use in Filter condition

### Module 1 → Module 3:
- `{{1.From Email}}` → Search value in Google Sheets

### Module 1 → Module 4:
- `{{1.Body Text}}` → Customer's reply in OpenAI prompt

### Module 3 → Module 4:
- `{{3.Name}}` → Original lead name
- `{{3.Business Name}}` → Original business
- `{{3.Industry}}` → Original industry
- `{{3.Problem}}` → Original problem
- `{{3.Budget}}` → Original budget

### Module 4 → Module 5:
- `{{4.Choices[1].Message.Content}}` → Email body

### Module 1 → Module 5:
- `{{1.From Email}}` → Email "To" address
- `{{1.Subject}}` → Reply subject

### Module 1 → Module 6:
- `{{1.Date}}` → Last Reply timestamp

### Module 3 → Module 6:
- `{{3.Row ID}}` → Which row to update

---

## Common Mistakes to Avoid

❌ **Wrong:** Using `{{1.Email}}` instead of `{{1.From Email}}`  
✅ **Right:** `{{1.From Email}}` is the correct field name

❌ **Wrong:** Not mapping variables in OpenAI prompt  
✅ **Right:** Click each `{{}}` and map to actual fields

❌ **Wrong:** Using wrong module number (e.g., `{{2.Name}}` when it's Module 3)  
✅ **Right:** Check module numbers - they're shown in Make.com

❌ **Wrong:** Forgetting to exclude your own email  
✅ **Right:** Add filter condition: From ≠ your email

❌ **Wrong:** Not running scenario once before mapping  
✅ **Right:** Run once first, then fields appear for mapping

---

## Testing Flow

```
1. Submit Typeform
   ↓
2. Wait for initial AI email (from Scenario 1)
   ↓
3. Reply to that email: "How much does this cost?"
   ↓
4. Wait 15 minutes (or trigger manually)
   ↓
5. Check inbox for AI reply
   ↓
6. Check Google Sheets - status updated?
   ↓
7. ✅ Success!
```

---

## Success Indicators

✅ **Module 1 turns green** = Found a reply email  
✅ **Module 2 turns green** = Passed safety checks  
✅ **Module 3 turns green** = Found the lead in Google Sheets  
✅ **Module 4 turns green** = AI generated a reply  
✅ **Module 5 turns green** = Email sent successfully  
✅ **Module 6 turns green** = Google Sheets updated  

If all 6 modules turn green, your automation is working! 🎉

---

Use this diagram alongside `MAKE_REPLY_AUTOMATION_EXACT_CONFIG.md` for the complete setup.
