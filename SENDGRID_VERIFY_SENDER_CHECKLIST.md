# SendGrid sender verification checklist (Step 3)

Your app sends intake emails from the address in **FROM_EMAIL** (in Railway or `.env`).  
That address **must** be verified in SendGrid, or SendGrid will not deliver.

---

## 1. See which address you use

- **Railway:** Project → your service → **Variables** → `FROM_EMAIL`  
  (e.g. `hello@lumo22.com` or `noreply@lumo22.com`)
- If `FROM_EMAIL` is not set, the app uses **noreply@lumo22.com** (see `config.py`).

The address below is the one that must be verified in SendGrid.

---

## 2. Log in to SendGrid

- Go to [https://app.sendgrid.com](https://app.sendgrid.com) and sign in.

---

## 3. Open Sender Authentication

- In the left menu: **Settings** → **Sender Authentication**.

---

## 4. Check Single Sender (or Domain)

**Option A – Single Sender (one “From” address)**  
- Under **Single Sender Verification**, check the list.  
- Your `FROM_EMAIL` (e.g. `hello@lumo22.com`) should appear and show as **Verified**.  
- If it is not in the list or not verified:  
  - Click **Verify a Single Sender**.  
  - Use exactly: **From Email Address** = your `FROM_EMAIL` (e.g. `hello@lumo22.com`).  
  - Fill the other required fields (From Name, Reply To, address, etc.).  
  - Send the verification email and click the link in that email to complete verification.

**Option B – Domain Authentication**  
- If you use **Domain Authentication** for `lumo22.com`, you can send from any `@lumo22.com` address (e.g. `hello@lumo22.com`, `noreply@lumo22.com`) as long as the domain shows as verified.  
- Under **Domain Authentication**, confirm that `lumo22.com` (or your sending domain) is **Verified**.

---

## 5. Confirm in SendGrid

- After verifying, the sender or domain should show a **Verified** status.  
- Sending from an unverified address triggers: *“The from address does not match a verified Sender Identity”* and the intake email will not be sent.

---

## Quick reference

| What to verify | Where in SendGrid |
|----------------|-------------------|
| Single “From” address | Settings → Sender Authentication → Single Sender Verification |
| Whole domain (e.g. lumo22.com) | Settings → Sender Authentication → Domain Authentication |

Your app’s **FROM_EMAIL** must match either a verified Single Sender or an address on a verified domain.
