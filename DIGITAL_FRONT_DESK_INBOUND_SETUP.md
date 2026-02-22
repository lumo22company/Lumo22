# Digital Front Desk — full automation setup

## 1. Supabase table (if not already done)

**Option A — Using the migration script (needs DATABASE_URL):**

1. In Supabase Dashboard → Settings → Database, copy the **Connection string (URI)** (Transaction pooler, e.g. port 6543).
2. Add to your `.env`:  
   `DATABASE_URL=postgresql://postgres.[ref]:[YOUR_PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres`
3. Run:  
   `python3 run_front_desk_migration.py`

**Option B — Using Supabase SQL Editor (no DATABASE_URL needed):**

1. Open Supabase Dashboard → **SQL Editor** → New query.
2. Paste the contents of `database_front_desk_setups.sql`.
3. Run the query.

This creates/updates the `front_desk_setups` table and the `forwarding_email` column.

---

## 2. SendGrid Inbound Parse (for auto-reply)

To have the app **auto-reply** to enquiries sent to each customer’s unique address:

1. In **SendGrid** go to **Settings** → **Inbound Parse**.
2. Add a **Host & URL**:
   - **Destination URL:** `https://lumo22.com/webhooks/sendgrid-inbound` (or your Railway URL: `https://lumo-22-production.up.railway.app/webhooks/sendgrid-inbound`).
   - **Domain:** your inbound domain, e.g. `inbound.lumo22.com` (must match `INBOUND_EMAIL_DOMAIN` in `.env`).
3. In your **DNS** (e.g. GoDaddy), add an **MX** record for that subdomain pointing to SendGrid (e.g. `mx.sendgrid.net`, priority 10). SendGrid’s Inbound Parse setup page shows the exact values.

After this, any email sent to a `reply-xxxxx@inbound.lumo22.com` address is posted to your app; the app looks up the customer, generates a reply with OpenAI, and sends it back.

---

## 3. What’s automated now

- **After payment:** Customer is emailed with a link to the setup form and a unique **forwarding address**.
- **After setup form:** Details are stored in Supabase; you get an email with the customer’s **forwarding address** and a “Mark as connected” link.
- **Customer instruction:** They are told to forward enquiries to their unique address for auto-reply.
- **Inbound email:** When someone emails (or is forwarded to) that address, the app generates a reply and sends it via SendGrid.

Ensure `OPENAI_API_KEY`, `SENDGRID_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, and `INBOUND_EMAIL_DOMAIN` are set in Railway (and locally in `.env`) for this to work.
