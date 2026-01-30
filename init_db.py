"""
Initialize Supabase database tables.
Creates the leads table if it doesn't exist.
"""
from supabase import create_client
from config import Config
import json

def init_database():
    """Initialize database schema"""
    
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("Supabase not configured. Skipping database initialization.")
        print("You can still use the system, but leads won't be persisted.")
        return
    
    try:
        client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        
        # SQL to create leads table
        # Note: Supabase uses PostgreSQL, so we'll use SQL
        # In production, you'd run this via Supabase SQL editor or migrations
        
        create_table_sql = """
        -- Leads table (for businesses using the system)
        CREATE TABLE IF NOT EXISTS leads (
            lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            service_type TEXT NOT NULL,
            message TEXT NOT NULL,
            source TEXT DEFAULT 'web_form',
            qualification_score INTEGER,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            booked_at TIMESTAMPTZ,
            booking_link TEXT,
            qualification_details JSONB,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Businesses table (for SaaS accounts)
        CREATE TABLE IF NOT EXISTS businesses (
            business_id TEXT PRIMARY KEY,
            business_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            service_types TEXT,
            status TEXT DEFAULT 'active',
            subscription_tier TEXT DEFAULT 'starter',
            api_key TEXT UNIQUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_login TIMESTAMPTZ
        );
        
        CREATE INDEX IF NOT EXISTS idx_leads_business_id ON leads(business_id);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_qualification_score ON leads(qualification_score);
        CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses(email);
        CREATE INDEX IF NOT EXISTS idx_businesses_api_key ON businesses(api_key);
        """
        
        print("=" * 60)
        print("DATABASE INITIALIZATION")
        print("=" * 60)
        print("\nPlease run this SQL in your Supabase SQL Editor:")
        print("\n" + create_table_sql)
        print("\n" + "=" * 60)
        print("\nAlternatively, you can create the table manually:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Run the SQL above")
        print("4. Or use the Supabase dashboard Table Editor to create manually")
        print("\n" + "=" * 60)
        
        # Try to verify table exists
        try:
            result = client.table('leads').select('lead_id').limit(1).execute()
            print("\n✓ Leads table exists and is accessible")
        except Exception as e:
            print(f"\n⚠ Leads table may not exist yet: {e}")
            print("Please create it using the SQL above or via Supabase dashboard")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("\nYou can still use the system, but leads won't be persisted to database.")
        print("Consider setting up Supabase or using an alternative storage method.")

if __name__ == '__main__':
    init_database()
