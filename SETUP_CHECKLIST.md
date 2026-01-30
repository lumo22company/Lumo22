# Lumo 22 – Setup checklist

Tick off each item as you do it (change `[ ]` to `[x]`).

---

## Part 1 – Get the app running

- [ ] **Terminal:** Open Terminal, go to project: `cd /Users/sophieoverment/LUMO22`
- [ ] **Venv:** Create and activate: `python3 -m venv venv` then `source venv/bin/activate`
- [ ] **Dependencies:** Install: `pip install -r requirements.txt`
- [ ] **OpenAI:** Get API key from https://platform.openai.com/api-keys (add billing if needed)
- [ ] **Supabase:** Create project at https://supabase.com (save database password)
- [ ] **Supabase credentials:** Project Settings → API → copy **Project URL** and **anon public** key
- [ ] **Supabase tables:** SQL Editor → New query → paste all of `supabase_setup.sql` → Run
- [ ] **Verify tables:** Table Editor shows `leads` and `businesses`
- [ ] **Create .env:** In Terminal: `cp .env.example .env`
- [ ] **Edit .env:** Set `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` (open `.env` in Cursor)
- [ ] **Check setup:** `python3 check_setup.py` – all required items show ✅
- [ ] **Run app:** `python3 app.py` then open http://localhost:5001 – landing page loads

---

## Part 2 – Product systems (after app is running)

- [x] **Initial Make scenario:** Google Sheets → OpenAI → Gmail (new lead gets first AI email) — *you have this*
- [ ] **Reply handling (Make.com):** Create scenario “AI Receptionist - Reply Handler” (when someone replies to the AI email: Gmail Watch → filter → OpenAI → Gmail send reply)
- [ ] **Test reply flow:** Submit Typeform, reply to AI email, confirm AI responds
- [ ] **Payment:** Set up Stripe (or Gumroad), create products (£79 / £149 / £299)
- [ ] **Payment links:** Get payment link(s), add activation link to initial AI email in Make.com
- [ ] **Test activation:** Typeform → email → activation link works
- [ ] **Client onboarding:** Create onboarding Typeform + “Active Clients” Google Sheet
- [ ] **Make.com onboarding:** New row in Active Clients → update lead, send welcome email
- [ ] **Stripe redirect:** Payment success redirects to onboarding form
- [ ] **Test end-to-end:** Test payment → onboarding form → welcome email
- [ ] **Typeform end screen:** Update main Typeform end message (expect AI reply)
- [ ] **Final test:** Run through initial flow, reply flow, activation, onboarding; check Make.com logs
- [ ] **Go live:** Activate Make.com scenarios, share Typeform, start outreach

---

## Quick commands (when you come back to the project)

In Terminal:

```bash
cd /Users/sophieoverment/LUMO22
source venv/bin/activate
python3 app.py
```

Then open **http://localhost:5001** in your browser.
