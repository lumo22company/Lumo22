# Supabase Table Setup - Step by Step

I've created a SQL file for you! Here's exactly what to do:

## 📋 Step-by-Step Instructions

### 1. Open Supabase SQL Editor
- Go to your Supabase project dashboard
- Click **"SQL Editor"** in the left sidebar
- Click **"New query"** button

### 2. Copy the SQL
- Open the file `supabase_setup.sql` in this folder
- Select ALL the text (Cmd+A or Ctrl+A)
- Copy it (Cmd+C or Ctrl+C)

### 3. Paste into Supabase
- Go back to Supabase SQL Editor
- Paste the SQL into the editor (Cmd+V or Ctrl+V)

### 4. Run the SQL
- Click the **"Run"** button (or press Cmd+Enter / Ctrl+Enter)
- You should see: "Success. No rows returned" or similar success message

### 5. Verify It Worked
- Look at the bottom of the results - you should see a table name "leads"
- OR go to **"Table Editor"** in the left sidebar
- You should see a table called **"leads"** with all the columns

## ✅ That's It!

Once you see the "leads" table in your Supabase dashboard, the database is ready!

## 🆘 Troubleshooting

**If you get an error:**
- Make sure you're in the SQL Editor (not Table Editor)
- Make sure you copied the ENTIRE SQL file
- Try running it again - some parts might already exist (that's okay)

**If the table already exists:**
- That's fine! The SQL uses "IF NOT EXISTS" so it won't break
- Just verify the table is there in Table Editor

## Next Step

After the table is created, get your Supabase credentials:
1. Go to **Project Settings** → **API**
2. Copy your **Project URL** and **anon public key**
3. Share them with me and I'll add them to your `.env` file!
