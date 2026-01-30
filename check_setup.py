#!/usr/bin/env python3
"""
Setup verification script.
Checks if all required configuration is in place.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_config():
    """Check configuration status"""
    print("=" * 60)
    print("SETUP VERIFICATION")
    print("=" * 60)
    print()
    
    issues = []
    warnings = []
    
    # Check .env file exists
    if not os.path.exists('.env'):
        issues.append("❌ .env file not found. Run: cp .env.example .env")
    else:
        print("✅ .env file exists")
    
    # Check required API keys
    print("\n📋 Required Configuration:")
    print("-" * 60)
    
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key or openai_key == 'sk-your-openai-api-key-here':
        issues.append("❌ OPENAI_API_KEY not configured")
        print("❌ OPENAI_API_KEY: Not set")
    else:
        masked = openai_key[:7] + "..." + openai_key[-4:] if len(openai_key) > 11 else "***"
        print(f"✅ OPENAI_API_KEY: {masked}")
    
    supabase_url = os.getenv('SUPABASE_URL')
    if not supabase_url or 'your-project' in supabase_url:
        issues.append("❌ SUPABASE_URL not configured")
        print("❌ SUPABASE_URL: Not set")
    else:
        print(f"✅ SUPABASE_URL: {supabase_url[:30]}...")
    
    supabase_key = os.getenv('SUPABASE_KEY')
    if not supabase_key or 'your-supabase' in supabase_key:
        issues.append("❌ SUPABASE_KEY not configured")
        print("❌ SUPABASE_KEY: Not set")
    else:
        masked = supabase_key[:10] + "..." if len(supabase_key) > 10 else "***"
        print(f"✅ SUPABASE_KEY: {masked}")
    
    # Check optional services
    print("\n📋 Optional Configuration:")
    print("-" * 60)
    
    calendly_key = os.getenv('CALENDLY_API_KEY')
    if not calendly_key or 'your-calendly' in calendly_key:
        warnings.append("⚠️  Calendly not configured (booking links will use email fallback)")
        print("⚠️  CALENDLY_API_KEY: Not set")
    else:
        print("✅ CALENDLY_API_KEY: Set")
    
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    if not sendgrid_key or 'SG.your' in sendgrid_key:
        warnings.append("⚠️  SendGrid not configured (emails won't be sent)")
        print("⚠️  SENDGRID_API_KEY: Not set")
    else:
        print("✅ SENDGRID_API_KEY: Set")
    
    twilio_sid = os.getenv('TWILIO_ACCOUNT_SID')
    if not twilio_sid or 'your-twilio' in twilio_sid:
        warnings.append("⚠️  Twilio not configured (SMS won't be sent)")
        print("⚠️  TWILIO_ACCOUNT_SID: Not set")
    else:
        print("✅ TWILIO_ACCOUNT_SID: Set")
    
    # Check Python packages
    print("\n📦 Python Dependencies:")
    print("-" * 60)
    
    required_packages = [
        'flask', 'openai', 'supabase', 'sendgrid', 'twilio'
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}: Installed")
        except ImportError:
            issues.append(f"❌ {package} not installed")
            print(f"❌ {package}: Not installed")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if issues:
        print("\n❌ CRITICAL ISSUES (must fix before running):")
        for issue in issues:
            print(f"  {issue}")
        print("\n💡 Next steps:")
        print("  1. Get your API keys (see QUICK_START.md)")
        print("  2. Edit .env file with your credentials")
        print("  3. Run this check again")
        return False
    else:
        print("\n✅ All required configuration is set!")
    
    if warnings:
        print("\n⚠️  OPTIONAL WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n💡 These are optional but recommended for full functionality")
    
    print("\n🚀 You're ready to go! Run: python app.py")
    return True

if __name__ == '__main__':
    success = check_config()
    sys.exit(0 if success else 1)
