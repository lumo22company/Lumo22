# Passkeys (WebAuthn) setup

1. **Database** — In Supabase → SQL Editor, run `database_webauthn_credentials.sql` (creates `webauthn_credentials` linked to `customers`).

2. **Deploy** — Push/deploy so `webauthn` is installed (`requirements.txt`) and the new routes are live.

3. **Production domains** — `rp_id` and allowed origins are derived from `BASE_URL` by default (strips `www.` for `rp_id` and adds a www/non-www sibling origin when possible).  
   If you use extra hosts (e.g. Railway preview), set in Railway / `.env`:
   - `WEBAUTHN_RP_ID=lumo22.com`
   - `WEBAUTHN_ORIGINS=https://www.lumo22.com,https://lumo22.com`

4. **User flow** — After email verification, customers can **Add passkey** under **Account → Account Information**. On **Log in**, they can use **Sign in with passkey** (email required first).

5. **Limits** — Login throttling still applies to password attempts; successful passkey sign-in clears the lockout for that email/IP pair.
