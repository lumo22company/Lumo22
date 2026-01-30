# How to Find Legacy Supabase Keys

The new publishable keys don't work with the Python client yet. We need the legacy "anon" key.

## Step-by-Step to Find Legacy Keys

1. **Go to Supabase Dashboard**
   - Make sure you're in your project

2. **Click on "Project Settings"** (gear icon ⚙️ in left sidebar)

3. **Click on "API"** (not "API Keys")

4. **Look for a section that says:**
   - "Project API keys" 
   - Or scroll down to find "anon" and "service_role" keys

5. **If you see tabs or sections, look for:**
   - A tab that says "API Keys" vs "Data API"
   - Or a link/button that says "Show legacy keys" or "Legacy keys"

6. **The legacy keys look like this:**
   - **anon public**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpucnF6ZW10b2Rxbnhjbm50ZHRiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzY4NzY4MDAsImV4cCI6MjA1MjQ1MjgwMH0.xxxxx` (very long string starting with `eyJ`)
   - **service_role**: (don't use this one - it's secret!)

7. **Copy the "anon" key** (the long one starting with `eyJ`)

## Alternative: Check the URL

Sometimes the legacy keys are shown in a different format. Look for:
- JWT tokens (long strings)
- Keys labeled "anon" and "public"
- Not the new format that starts with `sb_publishable_`

## If You Still Can't Find It

The legacy keys might be:
- In a different section of the API settings
- Under "Authentication" settings
- Or you might need to contact Supabase support

**Once you find the legacy "anon" key, paste it here and I'll update your `.env` file!**
