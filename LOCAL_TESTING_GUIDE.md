# Local Testing Guide - View Your Site Locally

You can test the Lumo 22 site locally before launching.

---

## Quick Method (Recommended)

### Run the Flask app

1. **Start the app:**
   ```bash
   cd /Users/sophieoverment/LUMO22
   python3 app.py
   # or: flask run
   ```
2. **Open in browser:** `http://localhost:5001` (or the port shown)
3. **Pricing page:** `http://localhost:5001/digital-front-desk#pricing`

---

## Testing Locally

### What Works Locally:
✅ Landing page, product pages, and pricing  
✅ All styling and colors  
✅ Button clicks (Stripe links)  
✅ Mobile responsiveness (resize browser window)  
✅ Setup forms, activate flow  

### What to Test:
- [ ] Landing page loads (`/`)
- [ ] Digital Front Desk page and pricing (`/digital-front-desk#pricing`)
- [ ] Activate flow (`/activate`)
- [ ] Captions page (`/captions`)
- [ ] Page looks good on mobile (resize browser)

---

## When You're Ready to Launch

1. Set env vars (Stripe, SendGrid, Supabase, etc.) in Railway
2. Deploy via `railway up` or Git
3. Configure SendGrid Inbound Parse and DNS MX record
4. Test payment flows end-to-end

---

## Quick Checklist

- [ ] Run `python3 app.py` (or `flask run`)
- [ ] Visit `http://localhost:5001` and `/digital-front-desk#pricing`
- [ ] Test Activate and Captions flows
- [ ] Check mobile view (resize browser)

**You're all set for local testing!**
