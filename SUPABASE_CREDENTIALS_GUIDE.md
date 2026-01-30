# Getting Your Supabase Credentials - Step by Step

After you've created the table, follow these steps to get your credentials.

## Step 6: Get Your Supabase Project URL

1. **Look at the left sidebar** in Supabase (the menu on the left side of the screen)
2. **Find and click** the icon that looks like a **gear/cog** ⚙️ or says **"Project Settings"**
   - It's usually at the bottom of the sidebar
   - If you don't see it, look for "Settings" or click your project name at the top
3. **You'll see a menu** with options like:
   - General
   - API
   - Database
   - Auth
   - etc.
4. **Click on "API"** (it should be one of the first options)
5. **You'll see a page** with different sections:
   - Project URL
   - API Keys
   - etc.
6. **Find the section called "Project URL"**
   - It will show something like: `https://xxxxxxxxxxxxx.supabase.co`
7. **Click the copy button** next to the Project URL (it looks like two overlapping squares 📋 or says "Copy")
8. **Save this somewhere** (like a text file or Notes app) - you'll need it in a moment

## Step 7: Get Your Supabase API Key (anon public key)

1. **Still on the same "API" page** (you should still be here from Step 6)
2. **Look for a section called "API Keys"** or "Project API keys"
3. **You'll see a few different keys listed:**
   - `anon` `public` (this is the one you need!)
   - `service_role` `secret` (DO NOT use this one - it's secret!)
4. **Find the one that says "anon" and "public"**
   - It's a very long string of letters and numbers
   - It might be partially hidden with dots (••••)
5. **Click the "Reveal" button** or eye icon 👁️ next to it to see the full key
6. **Click the copy button** 📋 next to the anon public key
7. **Save this somewhere** too (same place you saved the URL)

## Step 8: Share Your Credentials

Now you have two things:
- **Project URL** (looks like: `https://xxxxx.supabase.co`)
- **anon public key** (a long string of letters/numbers)

**Share both of these with me** and I'll add them to your `.env` file automatically!

You can paste them like this:
```
Project URL: https://xxxxx.supabase.co
anon key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Step 9: After I Add Them

Once I've added your credentials to the `.env` file, we'll:
1. Verify everything is set up correctly
2. Test the system
3. Start the server so you can use it!

---

## Visual Guide - What You're Looking For

### In Project Settings → API, you'll see:

```
Project URL
┌─────────────────────────────────────────┐
│ https://xxxxxxxxxxxxx.supabase.co  [📋] │  ← Copy this
└─────────────────────────────────────────┘

Project API keys
┌─────────────────────────────────────────┐
│ anon public                             │
│ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... │  ← Copy this
│ [👁️ Reveal] [📋 Copy]                  │
└─────────────────────────────────────────┘

service_role secret
┌─────────────────────────────────────────┐
│ •••••••••••••••••••••••••••••••••••••• │  ← DON'T use this!
└─────────────────────────────────────────┘
```

---

## Troubleshooting

**"I can't find Project Settings"**
- Look for a gear icon ⚙️ in the left sidebar
- Or click on your project name at the top
- Or look for "Settings" in the menu

**"I don't see the API option"**
- Make sure you clicked on "Project Settings" (not "Account Settings")
- The API option should be in the list on the left side of the settings page

**"The key is hidden with dots"**
- Click the "Reveal" button or eye icon 👁️
- Then copy the full key that appears

**"I see multiple keys, which one?"**
- Use the one labeled **"anon"** and **"public"**
- Do NOT use "service_role" or "secret" - those are for admin use only

---

Ready? Go to Step 6 and let me know when you have both the URL and the anon key!
