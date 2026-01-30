# Make.com Quick Reference Guide

Quick setup checklist and troubleshooting for your AI Receptionist automation.

## ✅ Setup Checklist

### Scenario 1: Initial Email Automation

- [ ] Google Sheets module: Watch Rows Added
- [ ] OpenAI module: Create Chat Completion
  - [ ] System message configured
  - [ ] Variables mapped (Name, Business, Industry, etc.)
  - [ ] Booking link included in prompt
- [ ] Gmail module: Send an Email
  - [ ] To: mapped from Google Sheets → Email
  - [ ] Body: mapped from OpenAI → Content
  - [ ] Subject: configured
- [ ] Google Sheets module: Update a Row
  - [ ] AI Response column updated
  - [ ] Status column = "Email sent"
- [ ] Scenario scheduled: Every 15 minutes (or 1-5 mins on paid)
- [ ] Scenario activated: ON

### Scenario 2: Reply Handler

- [ ] Gmail module: Watch Emails
  - [ ] Filter: Subject contains "Re:"
  - [ ] Filter: From ≠ your email
- [ ] Flow Control: Filter
  - [ ] Excludes unsubscribe/opt-out
  - [ ] Excludes your own emails
- [ ] Google Sheets: Get a Row
  - [ ] Finds lead by email address
- [ ] OpenAI: Create Chat Completion
  - [ ] System message for replies configured
  - [ ] Customer reply mapped
  - [ ] Original lead data mapped
- [ ] Gmail: Send an Email
  - [ ] Reply to original email
  - [ ] AI response as body
- [ ] Google Sheets: Update a Row
  - [ ] Tracks reply count
  - [ ] Updates status
- [ ] Scenario activated: ON

---

## 🔧 Common Issues & Fixes

### Issue: Emails not sending

**Check:**
1. Gmail connection in Make.com
2. Email module mapping (Body contents = OpenAI → Content)
3. Make.com execution logs for errors
4. Gmail "Sent" folder to confirm

**Fix:**
- Reconnect Gmail account
- Test email module separately
- Check OpenAI output format

---

### Issue: AI responses are generic

**Check:**
1. OpenAI prompt includes enough context
2. Variables are mapped correctly
3. Model being used (gpt-4o-mini vs gpt-4)

**Fix:**
- Add more lead details to prompt
- Include industry-specific context
- Test with different models

---

### Issue: Replies not triggering

**Check:**
1. Gmail "Watch Emails" is connected
2. Filter settings (Subject contains "Re:")
3. Make.com execution history

**Fix:**
- Test Gmail trigger manually
- Adjust filter criteria
- Check email threading (Re: in subject)

---

### Issue: Google Sheets not updating

**Check:**
1. Sheet permissions (Make.com has access)
2. Column names match exactly (case-sensitive)
3. Row ID is correct

**Fix:**
- Reconnect Google Sheets
- Verify column headers
- Test update module separately

---

### Issue: Make.com not triggering

**Check:**
1. Scenario is activated (green switch)
2. Scheduling is set (every 15 mins)
3. Free plan limits (100 tasks/month)

**Fix:**
- Activate scenario
- Check task usage
- Upgrade plan if needed

---

## 📝 OpenAI Prompt Templates

### Initial Email Prompt

```
You are an expert AI receptionist for a business automation service.

Write a friendly, professional email under 120 words that:
- Thanks the person by name
- Shows you understand their problem
- Explains that our AI system captures, qualifies and books leads automatically
- Positions it as faster and cheaper than a receptionist
- Makes activation feel simple and immediate
- Does NOT ask questions
- Does NOT ask them to reply
- Only directs them to activate the system

Lead details:
Name: {{Name}}
Business: {{Business Name}}
Industry: {{Industry}}
Problem: {{Problem}}
Urgency: {{Urgency}}
Budget: {{Budget}}

End the email with:
"You've just interacted with our AI receptionist system. This is exactly how your customers would experience it.

Activate your AI receptionist here: [YOUR ACTIVATION LINK]"
```

### Reply Handler Prompt

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

Customer's reply:
{{Customer Reply}}

Original enquiry details:
Name: {{Name}}
Business: {{Business Name}}
Industry: {{Industry}}
Problem: {{Problem}}
Budget: {{Budget}}

Activation Link: {{Activation Link}}

Write an appropriate response to their reply.
```

---

## 🔗 Module Mapping Reference

### Google Sheets → OpenAI

- `{{Name}}` → Google Sheets → Name
- `{{Business Name}}` → Google Sheets → Business Name
- `{{Industry}}` → Google Sheets → Industry
- `{{Problem}}` → Google Sheets → Problem
- `{{Urgency}}` → Google Sheets → Urgency
- `{{Budget}}` → Google Sheets → Budget

### OpenAI → Gmail

- `{{Body}}` → OpenAI → Choices → 1 → Message → Content

### Gmail → Google Sheets

- `{{Email}}` → Gmail → From Email
- `{{Subject}}` → Gmail → Subject
- `{{Body}}` → Gmail → Body Text

---

## ⚙️ Make.com Settings

### Scheduling Options

**Free Plan:**
- Minimum: Every 15 minutes
- Maximum: 100 tasks/month

**Paid Plans:**
- Minimum: Every 1 minute
- Higher task limits

### Error Handling

**Set up error notifications:**
1. Go to Scenario settings
2. Enable "Error notifications"
3. Add your email

**This alerts you if automation fails.**

---

## 📊 Monitoring

### Daily Checks

1. **Make.com execution logs** - Any errors?
2. **Gmail Sent folder** - Emails sending?
3. **Google Sheets** - New leads coming in?
4. **OpenAI usage** - Cost tracking

### Weekly Reviews

1. **AI response quality** - Tweak prompts if needed
2. **Conversion rates** - Leads → Activations
3. **Client feedback** - Adjust accordingly

---

## 🚀 Optimization Tips

1. **A/B test prompts** - Try different tones
2. **Industry-specific prompts** - Customize per niche
3. **Response time** - Upgrade plan for faster triggers
4. **Multi-channel** - Add SMS/WhatsApp later
5. **CRM integration** - Connect to HubSpot/Pipedrive

---

## 📞 Support Resources

- **Make.com Docs:** https://www.make.com/en/help
- **OpenAI API Docs:** https://platform.openai.com/docs
- **Gmail API:** https://developers.google.com/gmail/api

---

## ✅ Pre-Launch Checklist

- [ ] Both scenarios built and tested
- [ ] All modules connected correctly
- [ ] Variables mapped properly
- [ ] Test submission works end-to-end
- [ ] Test reply works end-to-end
- [ ] Google Sheets updating correctly
- [ ] Emails sending successfully
- [ ] Scenarios activated
- [ ] Error notifications enabled
- [ ] Monitoring set up

**You're ready to go live!** 🎉
