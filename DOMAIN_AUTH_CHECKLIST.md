# Domain authentication — do this once (≈10 min)

So emails from hello@lumo22.com land in the **inbox** instead of spam.

---

## Step 1: SendGrid — start domain auth

1. Go to **https://app.sendgrid.com** and log in.
2. Left menu: **Settings** → **Sender Authentication**.
3. Under **Domain Authentication**, click **Authenticate Your Domain** (or **Get Started**).
4. **Which DNS host do you use?** Choose the one where lumo22.com is managed (e.g. Cloudflare, GoDaddy, Namecheap, Google Domains, etc.). If unsure, skip — you’ll still get the records to add.
5. Enter your domain: **lumo22.com** (no www, no https).
6. Click **Next**. SendGrid will show you **2 or 3 DNS records** (usually CNAMEs) with:
   - **Host** (e.g. `url1234.lumo22.com` or `em1234.lumo22.com`)
   - **Value / Points to** (e.g. `url1234.sendgrid.net`)

Leave this tab open (or copy the records somewhere).

---

## Step 2: Add the records in your DNS

1. Log in to where **lumo22.com** DNS is managed (your registrar or DNS host).
2. Find **DNS** / **DNS records** / **Manage DNS** for lumo22.com.
3. For **each** record SendGrid showed:
   - **Type:** CNAME
   - **Name / Host:** paste exactly what SendGrid gave (e.g. `url1234` or `url1234.lumo22.com` — your host may add the domain automatically)
   - **Value / Target / Points to:** paste exactly what SendGrid gave (e.g. `url1234.sendgrid.net`)
   - TTL: default (e.g. 3600 or Auto) is fine
4. **Save** all records.

---

## Step 3: Verify in SendGrid

1. Back in SendGrid (Sender Authentication page).
2. Click **Verify** (or **I’ve added the records**).
3. If it says “Pending”, wait 5–15 minutes and try again. DNS can take up to 48 hours, but often works in minutes.
4. When it shows **Verified**, you’re done.

---

## Step 4: Test

Send another test: from your project folder run:

```bash
python3 test_sendgrid.py hello@lumo22.com
```

Check inbox (and spam). After domain auth, new mail should be more likely to land in the inbox.

---

**If you don’t know where lumo22.com DNS is:**  
Check your domain registrar (where you bought lumo22.com) or your hosting provider. DNS is usually under “DNS settings”, “Manage DNS”, or “Nameservers”.
