# Fix 404 on /captions, /terms etc.

If `lumo22.com/captions` returns 404 but `www.lumo22.com/captions` works, use the **www** domain everywhere.

## 1. Set BASE_URL to www

- **Railway** → your service → **Variables** → set `BASE_URL=https://www.lumo22.com` (no trailing slash)
- **Locally** (`.env`) → same: `BASE_URL=https://www.lumo22.com`
- Save; Railway will redeploy.

## 2. Update Stripe webhook

In Stripe Dashboard → your webhook destination → edit the URL to:
`https://www.lumo22.com/webhooks/stripe`

## 3. Why

GoDaddy forwarding sends `lumo22.com` → `www.lumo22.com`, but subpaths can 404 depending on setup. The **www** CNAME points straight to Railway, so all routes work. Using `https://www.lumo22.com` as your canonical BASE_URL fixes links in emails and pre-launch checks.

See **GODADDY_DNS_RAILWAY.md** for full DNS setup.
