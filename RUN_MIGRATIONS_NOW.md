# Run migrations (account dashboard + auto-reply)

## 1. Get your Supabase connection string

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Open your project → **Project Settings** (gear icon) → **Database**
3. Under **Connection string**, choose **URI**
4. Copy the URI (looks like `postgresql://postgres.[ref]:[YOUR-PASSWORD]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`)

## 2. Add to .env

Add this line to your `.env` file (replace with your actual URI and password):

```
DATABASE_URL=postgresql://postgres.xxxxxxxx:YOUR_PASSWORD@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
```

## 3. Run migrations

```bash
python3 run_account_and_auto_reply_migrations.py
```

This creates:
- **customers** table (for account dashboard)
- **auto_reply_enabled** and **skip_reply_domains** columns on `front_desk_setups`

---

## Or: run SQL manually in Supabase

If you prefer not to use DATABASE_URL:

1. Supabase → **SQL Editor** → **New query**
2. Paste and run **database_customers.sql**
3. Paste and run **database_front_desk_auto_reply.sql**
