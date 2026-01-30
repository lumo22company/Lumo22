# Phase 1: Quick Checklist

Use this as you build. Check off each item as you complete it.

## 📋 Setup Checklist

### Scenario Creation
- [ ] Created new scenario: "AI Receptionist - Reply Handler"

### Module 1: Gmail Watch
- [ ] Added Gmail → Watch Emails
- [ ] Connected Gmail account
- [ ] Filter: Subject contains "Re:"
- [ ] Filter: From ≠ my email
- [ ] Module turns green when tested

### Module 2: Safety Filter
- [ ] Added Flow Control → Filter
- [ ] Condition: Body does NOT contain "unsubscribe"
- [ ] Condition: Body does NOT contain "opt out"
- [ ] Condition: From ≠ my email
- [ ] Module configured

### Module 3: Google Sheets Lookup
- [ ] Added Google Sheets → Get a Row
- [ ] Connected Google account
- [ ] Spreadsheet: "AI Receptionist Leads"
- [ ] Search: Email = {{Gmail → From Email}}
- [ ] Tested and finds the lead row

### Module 4: OpenAI Reply Generator
- [ ] Added OpenAI → Create Chat Completion
- [ ] Connected OpenAI account
- [ ] Model: gpt-4o-mini (or gpt-3.5-turbo)
- [ ] System message pasted
- [ ] User message pasted
- [ ] All variables mapped:
  - [ ] {{Gmail → Body Text}}
  - [ ] {{Google Sheets → Name}}
  - [ ] {{Google Sheets → Business Name}}
  - [ ] {{Google Sheets → Industry}}
  - [ ] {{Google Sheets → Problem}}
  - [ ] {{Google Sheets → Budget}}
- [ ] Activation link added (or placeholder)
- [ ] Module generates reply when tested

### Module 5: Gmail Send Reply
- [ ] Added Gmail → Send an Email
- [ ] To: {{Gmail → From Email}}
- [ ] Subject: "Re: " + {{Gmail → Subject}}
- [ ] Body: {{OpenAI → Choices → Message → Content}}
- [ ] From Name: "AI Receptionist Team"
- [ ] Module sends email when tested

### Module 6: Google Sheets Update
- [ ] Added Google Sheets → Update a Row
- [ ] Spreadsheet: "AI Receptionist Leads"
- [ ] Row: {{Google Sheets → Row ID}}
- [ ] Status: "In conversation"
- [ ] Last Reply: {{Gmail → Date}}
- [ ] Module updates sheet when tested

### Testing
- [ ] Submitted Typeform with test email
- [ ] Received initial AI email
- [ ] Replied to that email
- [ ] Received AI-generated reply
- [ ] Google Sheets updated correctly
- [ ] No errors in execution log

### Activation
- [ ] Scenario turned ON
- [ ] Scheduling set (15 mins on free plan)
- [ ] Error notifications enabled (optional)

---

## 🎯 Module Flow Visual

```
[Gmail Watch] 
    ↓
[Safety Filter]
    ↓
[Google Sheets Lookup]
    ↓
[OpenAI Generate Reply]
    ↓
[Gmail Send Reply]
    ↓
[Google Sheets Update]
```

---

## ⚡ Quick Reference: Field Mappings

**From Gmail Watch:**
- `{{Gmail → From Email}}` → Use for: To address, Google Sheets search
- `{{Gmail → Subject}}` → Use for: Reply subject
- `{{Gmail → Body Text}}` → Use for: OpenAI prompt (customer's reply)
- `{{Gmail → Date}}` → Use for: Last Reply timestamp

**From Google Sheets Lookup:**
- `{{Google Sheets → Name}}` → Use for: OpenAI prompt
- `{{Google Sheets → Business Name}}` → Use for: OpenAI prompt
- `{{Google Sheets → Industry}}` → Use for: OpenAI prompt
- `{{Google Sheets → Problem}}` → Use for: OpenAI prompt
- `{{Google Sheets → Budget}}` → Use for: OpenAI prompt
- `{{Google Sheets → Row ID}}` → Use for: Update Row module

**From OpenAI:**
- `{{OpenAI → Choices → 1 → Message → Content}}` → Use for: Gmail body

---

## 🐛 Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Can't see Google Sheets fields | Run scenario once first |
| OpenAI invalid key | Check connection, verify API key |
| Gmail not sending | Reconnect Gmail, check "To" mapping |
| Can't find lead | Check email matches exactly in sheet |
| Infinite loop | Add filter to exclude your email |

---

## ✅ Done When:

- [ ] All 6 modules configured
- [ ] All variables mapped correctly
- [ ] Tested end-to-end successfully
- [ ] Scenario activated and running
- [ ] No errors in execution log

**You're ready for Phase 2!** 🚀
