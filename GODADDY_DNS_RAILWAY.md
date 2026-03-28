# Point lumo22.com and www to Railway (GoDaddy)

Use this so both **www.lumo22.com** and **lumo22.com** load your app. Your domains are already added in Railway; you only need to add/update DNS in GoDaddy.

---

## 1. Get the Railway target (if needed)

1. Go to [railway.app](https://railway.app) → your project → **Lumo 22** service.
2. Open **Settings** → **Networking** / **Domains**.
3. Note the **Railway host** for your app (e.g. `lumo-22-production.up.railway.app`).  
   For each custom domain, Railway may show the exact record type and value; use those if they differ from below.

---

## 2. Open DNS for lumo22.com in GoDaddy

1. Go to **https://dcc.godaddy.com** (or godaddy.com → **My Products**).
2. Find **lumo22.com** and click **DNS** or **Manage DNS**.

---

## 3. Add or update the **www** record

**If you see "Record name www conflicts with another record":**  
You already have a record for `www`. Do **not** add a new one — **edit** the existing one.

1. In the DNS record list, find the row where **Name** is `www` (or `www.lumo22.com`).
2. Click **Edit** (pencil icon) on that row.
3. Set **Type** to **CNAME** (if it isn’t already).
4. Set **Value / Points to** to: `lumo-22-production.up.railway.app`
5. Save.

---

**If you don’t have a www record yet:**

1. Click **Add** (or **Add New Record**).
2. **Type:** **CNAME**
3. **Name:** `www`
4. **Value / Points to:** `lumo-22-production.up.railway.app`
5. Save.

---

## 4. Make **lumo22.com** (no www) go to your site — use **Forwarding**

GoDaddy does **not** allow a CNAME for the root (`@`), so you can’t point the apex to Railway with a CNAME. Use **domain forwarding** instead: send `lumo22.com` → `https://www.lumo22.com`.

1. In GoDaddy, with **lumo22.com** open, go to **Forwarding** (or **Domain** → **Forwarding**).
2. Click **Add** or **Manage** for **Domain Forwarding**.
3. Set:
   - **Forward to:** `https://www.lumo22.com`
   - **Forward type:** **Permanent (301)** (recommended).
   - **Settings:** **Forward only** (not “Forward with masking”).
4. Save.

After DNS propagates, anyone opening **lumo22.com** will be redirected to **https://www.lumo22.com**.

---

## 5. Why GoDaddy “forwarding” alone may not fix `/captions` on the apex

- **Forwarding** only applies when traffic hits **GoDaddy’s** forwarding layer first.
- If your **@** (apex) DNS points **directly at Railway** (A/ALIAS/CNAME to `*.up.railway.app`), browsers talk to **Railway first** — GoDaddy forwarding is **never used** for those requests.
- The app **redirects** `lumo22.com` → `https://www.lumo22.com` (301, same path and query) so deep links work even when DNS bypasses GoDaddy.

**Still set forwarding in GoDaddy** (301, forward only, **https://www.lumo22.com** — not `http://`, which adds an extra hop). It helps visitors who resolve the apex through GoDaddy’s stack.

---

## 6. Use www in BASE_URL

Set **BASE_URL** to the canonical domain that works for all paths:
- **BASE_URL=https://www.lumo22.com** (recommended; www CNAME goes straight to Railway)

In **Railway** → Variables, set `BASE_URL=https://www.lumo22.com` (no trailing slash). Do the same in `.env` for local tests.

## 7. Check

- Wait 5–30 minutes (sometimes up to a few hours).
- Open **https://www.lumo22.com** and **https://lumo22.com** — both should load your app.
- Visiting **lumo22.com** should redirect to **https://www.lumo22.com**.

---

## Summary

| Type  | Name | Value |
|-------|------|--------|
| CNAME | `www` | `lumo-22-production.up.railway.app` |
| CNAME | `@`   | `lumo-22-production.up.railway.app` |

If Railway shows different values for your project, use those instead.
