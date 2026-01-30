# What you need to do

Everything that could be done on your computer (virtual environment, dependencies, `.env` file created from the example) is already done. Follow these steps in order.

---

## Step 1 – Get your OpenAI API key

1. In your browser, go to **https://platform.openai.com** and sign in (or sign up).
2. Add a payment method: profile (top right) → **Billing** → **Add payment method** (a few dollars is enough to start).
3. Go to **https://platform.openai.com/api-keys**.
4. Click **Create new secret key**, name it (e.g. Lumo22), then **Create**.
5. **Copy the key** (it starts with `sk-`) and paste it into Notes or somewhere safe — you’ll need it in Step 4.

---

## Step 2 – Create your Supabase project and get credentials

1. In your browser, go to **https://supabase.com** and sign in (or sign up, e.g. with GitHub).
2. Click **New project**.
   - **Name:** e.g. `lumo22`.
   - **Database password:** choose one and **save it** (you may need it later).
   - **Region:** pick one near you.
   - Click **Create new project** and wait until it says the project is ready.
3. Get your credentials:
   - In the left sidebar, click the **gear icon** → **Project Settings**.
   - Click **API** in the left menu.
   - Copy **Project URL** (e.g. `https://xxxxx.supabase.co`).
   - Under **Project API keys**, copy the **anon** **public** key (the long string).
   - Paste both into Notes — you’ll need them in Step 4.

---

## Step 3 – Create the database tables in Supabase

1. In Supabase, click **SQL Editor** in the left sidebar.
2. Click **New query**.
3. On your computer, open the file **`supabase_setup.sql`** in your LUMO22 folder (e.g. in Cursor).
4. Select all the text (Cmd+A), then copy (Cmd+C).
5. Back in Supabase, paste into the SQL editor (Cmd+V).
6. Click **Run** (or press Cmd+Enter).
7. Check: click **Table Editor** in the left sidebar. You should see tables named **leads** and **businesses**.

---

## Step 4 – Put your keys into the `.env` file

1. In Cursor, open the file **`.env`** in your LUMO22 project (same folder as `app.py`).  
   If you don’t see it, it may be hidden: use **File → Open** and choose `.env`, or use the file search.
2. Find these three lines and **replace** the placeholder values with your real ones (no extra spaces or quotes):

   - **OpenAI**  
     Change:  
     `OPENAI_API_KEY=sk-your-openai-api-key-here`  
     To:  
     `OPENAI_API_KEY=` then paste your OpenAI key from Step 1.

   - **Supabase URL**  
     Change:  
     `SUPABASE_URL=https://your-project.supabase.co`  
     To:  
     `SUPABASE_URL=` then paste your Project URL from Step 2.

   - **Supabase key**  
     Change:  
     `SUPABASE_KEY=your-supabase-anon-key-here`  
     To:  
     `SUPABASE_KEY=` then paste your anon public key from Step 2.

3. Save the file (Cmd+S).

---

## Step 5 – Check that everything is set up

1. Open **Terminal** (Cmd+Space, type `Terminal`, Enter).
2. Run these two lines (you can paste both, then press Enter once):

   ```bash
   cd /Users/sophieoverment/LUMO22
   source venv/bin/activate
   ```

3. Run:

   ```bash
   python3 check_setup.py
   ```

4. You should see **“All required configuration is set!”** and **“You’re ready to go!”**  
   If something shows as “Not set”, fix that line in `.env` and run `python3 check_setup.py` again.

---

## Step 6 – Start the app and open it in your browser

1. In the same Terminal window (still in the project folder with `(venv)` active), run:

   ```bash
   python3 app.py
   ```

2. You should see messages like “Services initialized successfully” and “Running on http://0.0.0.0:5001”.
3. Open your browser and go to: **http://localhost:5001**
4. You should see your Lumo 22 landing page.

To stop the app later: in the Terminal window where it’s running, press **Ctrl+C**.

---

## Summary

| Step | What you do |
|------|------------------|
| 1 | Get OpenAI API key (browser). |
| 2 | Create Supabase project and copy Project URL + anon key (browser). |
| 3 | In Supabase SQL Editor, paste and run `supabase_setup.sql`. |
| 4 | In Cursor, edit `.env` and paste in your three keys; save. |
| 5 | In Terminal: `cd` to project, `source venv/bin/activate`, then `python3 check_setup.py`. |
| 6 | In Terminal: `python3 app.py`, then open http://localhost:5001 in your browser. |

After that, the app is running and you can move on to the next parts of your product systems when you’re ready.

---

## Make.com – where you are

You already have: **Google Sheets → OpenAI → Gmail**. That’s the *initial* flow: when a new row lands in your sheet (e.g. from Typeform), Make triggers, OpenAI writes the first email, and Gmail sends it. That’s the “first touch” to new leads.

**Still optional:** A *second* scenario called **Reply Handler**: when someone *replies* to that AI email, Make watches Gmail, uses OpenAI to generate a reply, and sends it. So you’d have “first email” (done) + “reply to their reply” (separate scenario). See `COMPLETE_SETUP_ACTION_PLAN.md` or `SIMPLE_REPLY_AUTOMATION.md` for how to add it. Next after that is payment/activation (Stripe, link in email) and client onboarding.
