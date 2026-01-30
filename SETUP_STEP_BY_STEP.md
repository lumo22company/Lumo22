# Lumo 22 – Setup Step by Step (Assume I Know Nothing)

This guide gets your product systems running from zero. Do each step in order. If something fails, stop and fix it before continuing.

**Quick links:**
- **Checklist to tick off:** see **`SETUP_CHECKLIST.md`** in this folder.
- **Already did Terminal + OpenAI + Supabase?** Jump to **[Resume from here (after Supabase)](#resume-from-here-after-supabase)** below.

---

## What you’ll need

- A Mac (you’re on one).
- A web browser.
- About 20–30 minutes.
- You’ll create: an **OpenAI** account, a **Supabase** project, and a **`.env`** file in this project.

---

## What is the Terminal (and why are we using it)?

**Terminal** is an app on your Mac that lets you talk to your computer by typing instructions instead of clicking. It’s like a text-based control panel.

- **Why use it here?** Your Lumo 22 project is a small “server” — a program that runs in the background and sends web pages to your browser. There’s no “double-click to run” icon for that. So we use Terminal to:
  1. **Go to the project folder** – so the computer knows which code to run.
  2. **Install the right tools** – Python libraries this project needs (Flask, OpenAI, etc.).
  3. **Start the app** – one command tells the computer to run your site.

- **You’re not changing your Mac.** Everything we do stays inside your project folder. We’re not installing system-wide software or messing with settings.

- **What you’ll do:** Open Terminal, type (or paste) a short line of text, press Enter. The computer does the work and prints a result. That’s it. If you can type in a text box and press Enter, you can do this.

When the guide says “run this command” or “type this,” it means: type it in Terminal (or paste it), then press Enter.

---

## Part 1: Get the code running on your computer

### Step 1 – Open Terminal and go to your project

1. Open **Terminal** (Spotlight: press `Cmd + Space`, type `Terminal`, press Enter).
2. Go to your project folder. Type this (then press Enter):

   ```bash
   cd /Users/sophieoverment/LUMO22
   ```

3. Check you’re in the right place. Type:

   ```bash
   ls
   ```

   You should see files like `app.py`, `requirements.txt`, `.env.example`. If you do, you’re in the project folder.

---

### Step 2 – Create a Python virtual environment

A “virtual environment” keeps this project’s Python packages separate from the rest of your Mac.

1. In the same Terminal window, type:

   ```bash
   python3 -m venv venv
   ```

2. Press Enter. It may take a few seconds. You should get your prompt back with no error.
3. “Turn on” the virtual environment:

   ```bash
   source venv/bin/activate
   ```

4. Your prompt should now start with `(venv)`. From now on, whenever you open a new Terminal to work on this project, run:

   ```bash
   cd /Users/sophieoverment/LUMO22
   source venv/bin/activate
   ```

   before running any other commands below.

---

### Step 3 – Install dependencies

Still in Terminal (with `(venv)` active), run:

```bash
pip install -r requirements.txt
```

Wait until it finishes. You should see “Successfully installed …” for several packages. If you see an error, copy it and we can fix it.

---

## Part 2: Get your API keys and database

You need **two** things: an **OpenAI API key** (for the AI) and a **Supabase** project (for the database). Both have free tiers.

---

### Step 4 – Get your OpenAI API key

1. In your browser, go to: **https://platform.openai.com**
2. Sign up or log in.
3. **Add payment (required for API):**
   - Click your profile (top right) → **Billing** → **Add payment method**.
   - Add a card. You can set a low limit (e.g. $5). Usage for lead qualification is small (roughly a few cents per lead).
4. **Create an API key:**
   - Go to: **https://platform.openai.com/api-keys**
   - Click **“Create new secret key”**.
   - Give it a name (e.g. “Lumo22”) and create.
   - **Copy the key immediately.** It looks like `sk-proj-...` and is only shown once. Paste it somewhere safe (e.g. Notes) for the next step.

---

### Step 5 – Create your Supabase project and get credentials

1. In your browser, go to: **https://supabase.com**
2. Click **“Start your project”** and sign up / log in (e.g. with GitHub).
3. **Create a new project:**
   - Click **“New project”**.
   - **Name:** e.g. `lumo22` (or anything you like).
   - **Database password:** Choose a strong password and **save it** (you’ll need it to connect to the database later).
   - **Region:** Pick one close to you.
   - Click **“Create new project”** and wait 1–2 minutes until it says “Project is ready”.
4. **Get your Project URL and API key:**
   - In the left sidebar, click the **gear icon** → **Project Settings**.
   - Click **“API”** in the left menu.
   - You’ll see:
     - **Project URL** – e.g. `https://xxxxxxxxxxxxx.supabase.co`
     - **Project API keys** – two keys: “anon” (public) and “service_role” (secret).
   - Copy the **Project URL**.
   - Under **Project API keys**, copy the **“anon” “public”** key (the long string).  
     **Do not** use the “service_role” key in your app for normal use.
   - Paste both into Notes (or somewhere safe) for the next step.

---

### Step 6 – Create the database table in Supabase

Your app expects a `leads` table and a `businesses` table. Create them once in Supabase.

1. In Supabase, in the left sidebar, click **“SQL Editor”**.
2. Click **“New query”**.
3. Open the file **`supabase_setup.sql`** in your project (in Cursor or any text editor). It’s in the root folder: `/Users/sophieoverment/LUMO22/supabase_setup.sql`.
4. Select **all** the text in that file (Cmd+A), then copy (Cmd+C).
5. Back in Supabase SQL Editor, paste (Cmd+V) so the editor contains the full SQL.
6. Click **“Run”** (or press Cmd+Enter).
7. You should see a success message and, in the results, a row showing the `leads` table.  
   To double-check: click **“Table Editor”** in the left sidebar – you should see tables **`leads`** and **`businesses`**.

---

## Resume from here (after Supabase)

If you’ve already done **Terminal (venv + pip install)**, **OpenAI API key**, and **Supabase project** (and have your Supabase URL + anon key somewhere), continue from here.

1. **Supabase tables (if you haven’t already)**  
   Supabase → **SQL Editor** → **New query** → paste all of **`supabase_setup.sql`** → **Run**.  
   In **Table Editor** you should see `leads` and `businesses`.

2. **Create `.env`**  
   In Terminal: `cd /Users/sophieoverment/LUMO22`, then `source venv/bin/activate`, then:
   ```bash
   cp .env.example .env
   ```
   Open **`.env`** in Cursor and set:
   - `OPENAI_API_KEY=` (your OpenAI key)
   - `SUPABASE_URL=` (from Supabase → Project Settings → API)
   - `SUPABASE_KEY=` (Supabase **anon public** key)
   Save.

3. **Check setup**  
   In Terminal:
   ```bash
   python3 check_setup.py
   ```
   Fix any “Not set” in `.env` until it says “All required configuration is set!”

4. **Start the app**  
   In Terminal:
   ```bash
   python3 app.py
   ```
   Open **http://localhost:5001** in your browser. You should see the Lumo 22 landing page.

---

## Part 3: Connect the app to your keys and database

### Step 7 – Create and edit your `.env` file

The app reads secrets from a file named `.env`. You create it by copying the example and then filling in your real values.

1. In Terminal (still in `/Users/sophieoverment/LUMO22` with `(venv)` active), run:

   ```bash
   cp .env.example .env
   ```

2. Open the **`.env`** file in Cursor (it’s in the project root, same folder as `app.py`).
3. Find these three lines and **replace** the placeholder values with your real ones. Don’t add quotes unless the value already has them.

   - **OpenAI**  
     Replace `sk-your-openai-api-key-here` with the key you copied in Step 4:

     ```
     OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
     ```

   - **Supabase URL**  
     Replace `https://your-project.supabase.co` with your Project URL from Step 5:

     ```
     SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
     ```

   - **Supabase key**  
     Replace `your-supabase-anon-key-here` with the **anon public** key from Step 5:

     ```
     SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-long-key
     ```

4. Save the file (Cmd+S).  
   You can leave all other lines in `.env` as they are for now. Optional things (Calendly, SendGrid, Twilio) can be added later.

---

### Step 8 – Check that setup is correct

In Terminal (same folder, venv active), run:

```bash
python3 check_setup.py
```

- If you see **“All required configuration is set!”** and **“You’re ready to go!”**, continue to Step 9.
- If you see any **“Not set”** or **“not configured”** for `OPENAI_API_KEY`, `SUPABASE_URL`, or `SUPABASE_KEY`, fix those in `.env` and run `python3 check_setup.py` again.

---

### Step 9 – Start the app and open it in the browser

1. In Terminal, run:

   ```bash
   python3 app.py
   ```

2. You should see something like:
   - “Services initialized successfully”
   - “Configuration validated”
   - “Running on http://0.0.0.0:5001”

3. Open your browser and go to: **http://localhost:5001**  
   You should see your Lumo 22 landing page.  
   **Note:** The app runs on **port 5001**, not 5000.

4. To stop the app: in the Terminal window where it’s running, press **Ctrl+C**.

---

## You’re done with the basics

At this point you have:

- The app running locally.
- OpenAI and Supabase connected.
- The database tables (`leads` and `businesses`) created.

Next steps (when you’re ready) are in your product-systems plan: e.g. reply handling in Make.com, payment/activation, client onboarding, and go live. If you tell me which step you’re on, I can walk you through it in the same “assume I know nothing” style.

---

## Quick reference – commands to run each time

When you open a new Terminal to work on this project:

```bash
cd /Users/sophieoverment/LUMO22
source venv/bin/activate
python3 app.py
```

Then open **http://localhost:5001** in your browser.

---

## If something goes wrong

- **“python3: command not found”**  
  Install Python 3 from https://www.python.org/downloads/ or via Homebrew (`brew install python`).

- **“No module named 'flask'” (or similar)**  
  Make sure you ran `source venv/bin/activate` and then `pip install -r requirements.txt` in the same Terminal.

- **“Address already in use”**  
  The app is already running in another Terminal, or another program is using port 5001. Close the other app or run: `lsof -i :5001` then `kill -9 <PID>` (replace `<PID>` with the number from the first column).

- **OpenAI or Supabase errors**  
  Run `python3 check_setup.py` again and fix any missing or wrong values in `.env`. Make sure there are no extra spaces or quotes around the key values.
