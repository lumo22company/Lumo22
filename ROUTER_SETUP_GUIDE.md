# Router Setup Guide (Using Router Instead of Filter)

Since you have Router available (not Filter), here's exactly how to set it up.

---

## Visual Flow

```
[Gmail Watch]
    ↓
[Router]
    ├─→ Route 1: "Continue" (passes all checks)
    │       ↓
    │   [Google Sheets Lookup]
    │       ↓
    │   [OpenAI Generate Reply]
    │       ↓
    │   [Gmail Send Reply]
    │       ↓
    │   [Google Sheets Update]
    │
    └─→ Route 2: "Stop" (fails checks)
            ↓
        (Nothing - flow stops here)
```

---

## Step-by-Step Router Configuration

### 1. Add Router Module
- Click **"+"** after Gmail module
- Select **"Flow control"** → **"Router"**

### 2. Configure Route 1: "Continue"

**This route handles emails that PASS all safety checks.**

1. Router will show **"Route 1"** - click on it
2. Name it: **"Continue"** (optional, but helpful)
3. Click **"Set up a filter"** or **"Add condition"**

**Add 3 Conditions (ALL must be true to continue):**

**Condition 1:**
- Field: `{{1.Body Text}}` (map from Gmail module)
- Operator: `Does not contain`
- Value: `unsubscribe`

**Condition 2:**
- Click "Add condition"
- Field: `{{1.Body Text}}` (map from Gmail module)
- Operator: `Does not contain`
- Value: `opt out`

**Condition 3:**
- Click "Add condition"
- Field: `{{1.From Email}}` (map from Gmail module)
- Operator: `Does not equal`
- Value: `[YOUR EMAIL ADDRESS]` (the email you send AI emails from)

### 3. Configure Route 2: "Stop"

**This route handles emails that FAIL any safety check.**

1. Router will show **"Route 2"** - click on it
2. Name it: **"Stop"** (optional)
3. **Leave this route completely EMPTY**
   - Don't add any modules
   - Don't connect anything to it
   - This stops the flow (no reply sent)

### 4. Connect Your Modules

**IMPORTANT:** Connect all your remaining modules to **Route 1 (Continue)**:

```
Route 1 (Continue)
    ↓
[Google Sheets → Get a Row]
    ↓
[OpenAI → Create Chat Completion]
    ↓
[Gmail → Send an Email]
    ↓
[Google Sheets → Update a Row]
```

**Route 2 (Stop)** should have nothing connected.

---

## How It Works

### Example 1: Good Email (Goes to Continue Route)
- Email from: `customer@example.com`
- Subject: `Re: Your enquiry`
- Body: `How much does this cost?`
- **Result:** ✅ Passes all 3 checks → Goes to Route 1 → Gets AI reply

### Example 2: Unsubscribe Email (Goes to Stop Route)
- Email from: `customer@example.com`
- Subject: `Re: Your enquiry`
- Body: `Please unsubscribe me`
- **Result:** ❌ Fails check (contains "unsubscribe") → Goes to Route 2 → No reply sent

### Example 3: Your Own Email (Goes to Stop Route)
- Email from: `your-email@gmail.com` (your sending address)
- Subject: `Re: Your enquiry`
- Body: `Test message`
- **Result:** ❌ Fails check (from your email) → Goes to Route 2 → No reply sent

---

## Common Mistakes

❌ **Wrong:** Connecting modules to Route 2 (Stop)
- This would send replies to unsubscribe emails!

✅ **Right:** Only connect modules to Route 1 (Continue)

❌ **Wrong:** Leaving Route 1 empty
- This would never send any replies!

✅ **Right:** Connect all modules to Route 1

❌ **Wrong:** Using "contains" instead of "does not contain"
- This would only reply to unsubscribe emails!

✅ **Right:** Use "does not contain" for unsubscribe/opt-out

---

## Testing

1. **Test Route 1 (Continue):**
   - Reply to an AI email with: "How much does this cost?"
   - Should go to Route 1 → Get AI reply

2. **Test Route 2 (Stop):**
   - Reply with: "Please unsubscribe me"
   - Should go to Route 2 → No reply sent

3. **Test Route 2 (Stop):**
   - Send email from your own address
   - Should go to Route 2 → No reply sent

---

## Quick Reference

| Route | Conditions | What Happens |
|-------|------------|--------------|
| Route 1: Continue | Body ≠ "unsubscribe"<br>Body ≠ "opt out"<br>From ≠ your email | ✅ Gets AI reply |
| Route 2: Stop | Any condition fails | ❌ No reply sent |

---

## Next Steps

After Router is configured:
1. ✅ Router module complete
2. Continue to **Module 3:** Google Sheets → Get a Row
3. Connect Module 3 to **Route 1 (Continue)**, not Route 2!

**You're doing great!** 🎉
