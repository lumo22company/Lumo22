# Test the Account Dashboard

## 1. Create the customers table (one-time)

**Option A – Migration script (needs DATABASE_URL)**

Add to `.env`:
```
DATABASE_URL=postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres
```
(Get from: Supabase Dashboard → Project Settings → Database → Connection string → URI)

Then run:
```bash
python3 run_customers_migration.py
```

**Option B – Supabase SQL Editor**

1. Supabase Dashboard → SQL Editor → New query
2. Paste contents of `database_customers.sql`
3. Run

## 2. Start the app

```bash
python app.py
# or: flask run
```

## 3. Test the dashboard

1. **Sign up:** http://localhost:5001/signup  
   - Enter email + password (min 6 chars) → Create account → redirects to `/account`

2. **Log in:** http://localhost:5001/login  
   - Enter same email + password → redirects to `/account`

3. **Dashboard:** http://localhost:5001/account  
   - Shows your email, DFD/Chat setups, Caption orders (linked by customer_email)

## 4. Live site

Same flow at `https://your-railway-url.up.railway.app/signup` (after deploy).
