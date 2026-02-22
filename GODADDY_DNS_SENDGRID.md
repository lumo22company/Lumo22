# Add SendGrid DNS records in GoDaddy

Use this when SendGrid has given you CNAME records to add for **lumo22.com**. Have the SendGrid page open so you can copy the **Host** and **Value** (Points to) for each record.

---

## 1. Open DNS for lumo22.com in GoDaddy

1. Go to **https://dcc.godaddy.com** (or log in at godaddy.com → **My Products**).
2. Find **lumo22.com** and click it.
3. Under **DNS** (or **Manage DNS**), click **Manage DNS** (or **DNS**).
4. You’ll see a list of existing records (A, CNAME, MX, etc.). Scroll to the bottom or find **Add** / **Add New Record**.

---

## 2. Add each CNAME record from SendGrid

SendGrid shows 2–3 records (domain auth) and possibly 1 more (link branding). Add **one record at a time** like this:

### Add a CNAME record

1. Click **Add** (or **Add Record**).
2. **Type:** choose **CNAME**.
3. **Name** (or **Host**):
   - SendGrid often shows something like **`em1234`** or **`url5678`** (just the subdomain).
   - In GoDaddy, enter **only that part** (e.g. `em1234`). GoDaddy will treat it as `em1234.lumo22.com`.
   - If SendGrid shows the full host (e.g. `em1234.lumo22.com`), use only the part before `.lumo22.com` (e.g. `em1234`).
   - **Do not** put `lumo22.com` in the Name field; GoDaddy adds the domain.
4. **Value** (or **Points to** / **Data**):
   - Copy **exactly** from SendGrid (e.g. `u1234567.wl.sendgrid.net` or `url1234.sendgrid.net`).
   - No `https://`, no trailing dot, no spaces.
5. **TTL:** leave default (e.g. 1 Hour or 600).
6. Click **Save**.

Repeat for **every** CNAME record SendGrid listed (domain auth + link branding if you chose Yes).

---

## 3. Check the records

Back on the DNS list you should see new rows like:

| Type  | Name   | Value                    |
|-------|--------|---------------------------|
| CNAME | em1234 | u1234567.wl.sendgrid.net |
| CNAME | url5678 | url5678.sendgrid.net    |

(Your names and values will be what SendGrid gave you.)

---

## 4. Verify in SendGrid

1. Go back to SendGrid → **Sender Authentication**.
2. Click **Verify** (or **I’ve added the records**).
3. If it says “Pending”, wait 5–15 minutes and try again. DNS can take up to 48 hours but often updates in minutes.

---

## GoDaddy quirks

- **Name field:** Use only the subdomain (e.g. `em1234`), not the full hostname. GoDaddy appends `.lumo22.com`.
- **No @ in Name:** For CNAMEs you’re adding a subdomain, so Name is something like `em1234`, not `@`.
- **Link branding:** If you added link branding, SendGrid will show a CNAME like `url1234` → `url1234.sendgrid.net`. Add it the same way: Type CNAME, Name = `url1234`, Value = `url1234.sendgrid.net`.

If you paste the **exact Host and Value** from your SendGrid screen (with the real IDs redacted if you like), I can double-check the format for GoDaddy.
