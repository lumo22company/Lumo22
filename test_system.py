#!/usr/bin/env python3
"""
Test script to verify the system is working correctly.
Run this after setting up your API keys.
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def test_imports():
    """Test that all required packages are installed"""
    print("Testing imports...")
    try:
        import flask
        import openai
        import supabase
        print("✅ All packages imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("\nTesting configuration...")
    from config import Config
    
    issues = []
    
    if not Config.OPENAI_API_KEY or 'your-openai' in Config.OPENAI_API_KEY:
        issues.append("OPENAI_API_KEY not configured")
    else:
        print("✅ OpenAI API key configured")
    
    if not Config.SUPABASE_URL or 'your-project' in Config.SUPABASE_URL:
        issues.append("SUPABASE_URL not configured")
    else:
        print("✅ Supabase URL configured")
    
    if not Config.SUPABASE_KEY or 'your-supabase' in Config.SUPABASE_KEY:
        issues.append("SUPABASE_KEY not configured")
    else:
        print("✅ Supabase key configured")
    
    if issues:
        print(f"\n⚠️  Configuration issues: {', '.join(issues)}")
        return False
    
    return True

def test_openai():
    """Test OpenAI connection"""
    print("\nTesting OpenAI connection...")
    try:
        from services.ai_qualifier import AIQualifier
        qualifier = AIQualifier()
        
        # Test qualification
        result = qualifier.qualify_lead(
            name="Test Lead",
            email="test@example.com",
            phone="+1234567890",
            service_type="Consultation",
            message="I need help with my project urgently. Budget is around $5000."
        )
        
        if result and 'qualification_score' in result:
            print(f"✅ OpenAI working! Test score: {result['qualification_score']}/100")
            print(f"   Intent: {result.get('intent_level', 'N/A')}")
            print(f"   Urgency: {result.get('urgency', 'N/A')}")
            return True
        else:
            print("❌ OpenAI returned unexpected format")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return False

def test_supabase():
    """Test Supabase connection"""
    print("\nTesting Supabase connection...")
    try:
        from services.crm import CRMService
        crm = CRMService()
        
        # Try to query (should work even if table is empty)
        leads = crm.get_all_leads(limit=1)
        print(f"✅ Supabase connected! Found {len(leads)} leads in database")
        return True
        
    except Exception as e:
        print(f"❌ Supabase test failed: {e}")
        print("   Make sure:")
        print("   1. SUPABASE_URL and SUPABASE_KEY are correct")
        print("   2. The 'leads' table exists (run SQL from init_db.py)")
        return False

def test_lead_model():
    """Test lead model validation"""
    print("\nTesting lead model...")
    try:
        from models.lead import Lead
        
        # Test valid lead
        lead = Lead(
            name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            service_type="Consultation",
            message="I need help with my project"
        )
        
        is_valid, error = lead.validate()
        if is_valid:
            print("✅ Lead model validation working")
            return True
        else:
            print(f"❌ Lead validation failed: {error}")
            return False
            
    except Exception as e:
        print(f"❌ Lead model test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("SYSTEM TEST SUITE")
    print("=" * 60)
    print()
    
    tests = [
        ("Package Imports", test_imports),
        ("Configuration", test_config),
        ("Lead Model", test_lead_model),
    ]
    
    # Only test APIs if keys are configured
    if os.getenv('OPENAI_API_KEY') and 'your-openai' not in os.getenv('OPENAI_API_KEY', ''):
        tests.append(("OpenAI API", test_openai))
    
    if (os.getenv('SUPABASE_URL') and 'your-project' not in os.getenv('SUPABASE_URL', '') and
        os.getenv('SUPABASE_KEY') and 'your-supabase' not in os.getenv('SUPABASE_KEY', '')):
        tests.append(("Supabase Database", test_supabase))
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your system is ready to use.")
        print("   Run: python app.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
