# Sign in with Apple (web) — Lumo 22

Your app already implements the flow. You need an **Apple Developer Program** membership (paid) and the items below.

**Return URL (exact):** `https://www.lumo22.com/api/auth/oauth/apple/callback`  
(Add a Railway preview URL the same way if you test on a staging domain.)

---

## 1. App ID (primary)

Apple links the **website** Services ID to an **App ID** that has Sign in with Apple enabled.

1. [Apple Developer](https://developer.apple.com/account/) → **Certificates, Identifiers & Profiles** → **Identifiers**.
2. **+** → **App IDs** → **App**.
3. **Description:** e.g. `Lumo 22 Sign in with Apple`.
4. **Bundle ID:** **Explicit**, e.g. `com.lumo22.signin` (use your own reverse-DNS string; it does not need to match a shipped iOS app).
5. Under **Capabilities**, enable **Sign In with Apple**.
6. **Continue** → **Register**.

---

## 2. Services ID (this is your “client id” for the web)

1. **Identifiers** → **+** → **Services IDs** → **Continue**.
2. **Description:** e.g. `Lumo 22 Web`.
3. **Identifier:** e.g. `com.lumo22.web` — this string is **`APPLE_OAUTH_CLIENT_ID`** in Railway.
4. Enable **Sign In with Apple** → **Configure**.
5. **Primary App ID:** choose the App ID from step 1.
6. **Website URLs:**
   - **Domains and Subdomains:** `www.lumo22.com` (no `https://`, no path).
   - **Return URLs:**  
     `https://www.lumo22.com/api/auth/oauth/apple/callback`  
     (must match character-for-character, including `https` and `www` if that is what you use in production.)
7. **Save** → **Continue** → **Register**.

Apple may ask you to **verify the domain** (`www.lumo22.com`). Follow their instructions (host a file or DNS record on that host).

---

## 3. Key (.p8) for the client secret JWT

1. **Keys** → **+**.
2. **Key Name:** e.g. `Lumo 22 Apple Sign In`.
3. Enable **Sign In with Apple** → **Configure** → pick the **same Primary App ID** as in step 2.
4. **Save** → **Continue** → **Register** → **Download** the `.p8` file (you only get it once).

Note:

- **Key ID** → **`APPLE_OAUTH_KEY_ID`**
- **Team ID** (top right of the membership page, or **Membership details**) → **`APPLE_OAUTH_TEAM_ID`**

---

## 4. Railway variables

Add to the **same** web service as Google OAuth:

| Variable | Value |
|----------|--------|
| `APPLE_OAUTH_CLIENT_ID` | Services ID identifier, e.g. `com.lumo22.web` |
| `APPLE_OAUTH_TEAM_ID` | 10-character Team ID |
| `APPLE_OAUTH_KEY_ID` | Key ID from the key you created |
| `APPLE_OAUTH_PRIVATE_KEY` | Full contents of the `.p8` file. In Railway, paste as **one line** with `\n` where line breaks were, **or** use `APPLE_OAUTH_PRIVATE_KEY_B64` instead (recommended below). |
| `APPLE_OAUTH_PRIVATE_KEY_B64` | (Optional) Base64 encoding of the **entire** `.p8` file (raw bytes). Easier than escaping newlines. If set, it overrides `APPLE_OAUTH_PRIVATE_KEY`. |

Aliases also work: `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID` (see `config.py`).

**Generate base64 (on your Mac, in the folder with the .p8 file):**

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy
```

Paste the clipboard into **`APPLE_OAUTH_PRIVATE_KEY_B64`** in Railway (single line, no quotes).

---

## 5. Deploy and test

1. **Redeploy** the service after saving variables.
2. Open **`https://www.lumo22.com/oauth-config-check`** — **Apple** should say **Yes**.
3. On **`/login`** and **`/signup`**, use **Continue with Apple**.

---

## Troubleshooting

| Symptom | Check |
|--------|--------|
| Apple page shows invalid redirect / config | Return URL in Apple **exactly** matches production URL; domain verified. |
| `oauth_error=token` in our app | Wrong Team ID, Key ID, Services ID, or `.p8` / base64; or key not linked to the same Primary App ID. |
| Email missing on second login | Expected: we identify returning users by Apple `sub`; first sign-in must complete account creation. |

Database: run **`database_customers_oauth.sql`** if you have not already (`apple_sub` column).
