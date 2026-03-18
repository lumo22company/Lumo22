# Captions not on account / PDF never sent — do this

Follow these steps **in order**.

---

## Step 1: Get the token from your intake email

1. Open the email you got after paying (subject like “Complete your form” or “Your 30 Days Captions”).
2. Click **“Complete the form”** (or copy the link).
3. The URL will look like:
   ```
   https://www.lumo22.com/captions-intake?t=abc123XYZ_def456...
   ```
4. **Copy only the token**: the part after `?t=` and before the next `&` (if any).  
   Example: if the link is `https://www.lumo22.com/captions-intake?t=Abc12XyZ-34`, your token is `Abc12XyZ-34`.

---

## Step 2: Run the fix-and-retry script on your computer

You need the project on your machine with a `.env` that has **Supabase**, **SendGrid**, and **Anthropic** (or OpenAI) keys.

1. Open Terminal (or Command Prompt).
2. Go to the project folder:
   ```bash
   cd /path/to/LUMO22
   ```
3. Run (replace `YOUR_TOKEN` with the token you copied):
   ```bash
   python3 scripts/fix_and_retry_caption_delivery.py YOUR_TOKEN
   ```
4. Wait for it to finish. It will:
   - Fix the order so it appears under your account (lowercase email).
   - Generate the captions and send the PDF to the email on the order.

If you see an error (e.g. missing API key), fix that in `.env` and run the command again.

---

## Step 3: Check email and account

1. Check the **inbox** (and **spam/junk**) for the delivery email with the PDF.
2. Refresh your **account/history page** — the order should now appear.

---

## If you don’t have the intake link anymore

- Check **all** emails from Lumo 22 / your payment receipt.
- If you really don’t have it: in **Supabase** → **Table Editor** → **caption_orders**, find your order (e.g. by your email or date), copy the **token** from that row, then run Step 2 with that token.

---

## If the script says “No order found for this token”

- Make sure you copied the **whole** token (no spaces, no missing characters).
- Token is in the URL after `?t=` when you open the intake form link.

## If the script says “This order has no intake data”

- You must **submit** the intake form at least once (click “Send details” at the end).
- Then run the script again with the same token.
