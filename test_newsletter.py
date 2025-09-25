#!/usr/bin/env python3
"""
Test script for Newsletter Graph API integration.
Run this to verify the setup is working correctly.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_environment():
    """Test that all required environment variables are present."""
    print("🔧 Testing Environment Configuration...")

    required_vars = [
        'TENANT_ID', 'CLIENT_ID',  # Removed CLIENT_SECRET for delegated auth
        'NEWSLETTER_USER', 'NEWSLETTER_FOLDER'
    ]

    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False

    print("✅ All environment variables are set")
    print(f"   TENANT_ID: {os.environ.get('TENANT_ID', 'Not set')}")
    print(f"   CLIENT_ID: {os.environ.get('CLIENT_ID', 'Not set')}")
    print(f"   GRAPH_SCOPE: {os.environ.get('GRAPH_SCOPE', 'Mail.Read (default)')}")
    return True

def test_imports():
    """Test that all newsletter services can be imported."""
    print("📦 Testing Service Imports...")

    try:
        from services.graph_auth import GraphAuthManager
        print("✅ GraphAuthManager imported")

        from services.graph_client import GraphClient
        print("✅ GraphClient imported")

        from services.newsletter_sanitizer import NewsletterSanitizer
        print("✅ NewsletterSanitizer imported")

        from services.newsletter_ingest import NewsletterIngestService
        print("✅ NewsletterIngestService imported")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_authentication():
    """Test Graph API authentication."""
    print("🔐 Testing Graph API Authentication...")
    print("⚠️  Note: This may trigger device code flow if no cached tokens exist")

    try:
        from services.graph_auth import GraphAuthManager

        auth_manager = GraphAuthManager()

        # Check cache info first
        cache_info = auth_manager.get_cache_info()
        print(f"   Token cache exists: {cache_info.get('cache_file_exists', False)}")
        print(f"   Cached accounts: {cache_info.get('accounts_count', 0)}")

        if cache_info.get('accounts_count', 0) > 0:
            print("   Attempting silent token acquisition...")
        else:
            print("   No cached accounts - this will trigger device code flow")
            print("   You may need to authenticate as nyhetsbrev@gronvoldmaskin.no")

        token = auth_manager.get_token()

        if token:
            print("✅ Successfully acquired access token")
            print(f"   Token length: {len(token)} characters")
            return True
        else:
            print("❌ Failed to acquire access token")
            return False

    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False

def test_graph_client():
    """Test Graph API client functionality."""
    print("📡 Testing Graph Client...")

    try:
        from services.graph_client import GraphClient

        client = GraphClient()

        # Test simple Graph API call
        result = client.graph_get("me")  # This should fail gracefully for application auth

        # Test newsletter sync (this will attempt actual API calls)
        print("📧 Testing newsletter synchronization (this may take a few seconds)...")
        newsletters = client.sync_newsletters()

        print(f"✅ Graph client test completed. Found {len(newsletters)} newsletters")
        return True

    except Exception as e:
        print(f"❌ Graph client error: {e}")
        return False

def test_sanitizer():
    """Test HTML sanitization."""
    print("🧹 Testing HTML Sanitization...")

    try:
        from services.newsletter_sanitizer import NewsletterSanitizer

        sanitizer = NewsletterSanitizer()

        # Test HTML sanitization
        dangerous_html = """
        <div>
            <h1>Test Newsletter</h1>
            <script>alert('dangerous');</script>
            <p>This is safe content</p>
            <iframe src="evil.com"></iframe>
        </div>
        """

        clean_html = sanitizer.sanitize_html(dangerous_html)

        if '<script>' not in clean_html and '<iframe>' not in clean_html:
            print("✅ HTML sanitization working correctly")
            return True
        else:
            print("❌ HTML sanitization failed - dangerous content not removed")
            return False

    except Exception as e:
        print(f"❌ Sanitization error: {e}")
        return False

def test_token_cache():
    """Test token cache functionality."""
    print("💾 Testing Token Cache Management...")

    try:
        from services.graph_auth import GraphAuthManager

        auth_manager = GraphAuthManager()

        # Get cache info
        cache_info = auth_manager.get_cache_info()

        print(f"   Cache file exists: {cache_info.get('cache_file_exists', False)}")
        print(f"   Accounts in cache: {cache_info.get('accounts_count', 0)}")

        if cache_info.get('accounts'):
            for i, account in enumerate(cache_info['accounts']):
                print(f"   Account {i+1}: {account.get('username', 'Unknown')}")

        # Test cache operations
        if cache_info.get('cache_file_exists', False):
            print("✅ Token cache is working")
            return True
        else:
            print("⚠️  No token cache file found (normal on first run)")
            return True  # Not an error condition

    except Exception as e:
        print(f"❌ Token cache error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Newsletter Feature Test Suite")
    print("=" * 50)

    tests = [
        ("Environment", test_environment),
        ("Imports", test_imports),
        ("Token Cache", test_token_cache),
        ("HTML Sanitizer", test_sanitizer),
        ("Authentication", test_authentication),  # Moved to end as it may trigger device flow
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print()
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
            print()

    # Summary
    print("📋 Test Summary")
    print("=" * 50)

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print()
    print(f"Overall: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All tests passed! Newsletter feature is ready.")
    else:
        print("⚠️  Some tests failed. Check the setup guide in NEWSLETTER_SETUP.md")

    # Important notes for delegated authentication
    print("\n📝 Important Notes:")
    print("• Authentication test may trigger device code flow on first run")
    print("• You'll need credentials for nyhetsbrev@gronvoldmaskin.no")
    print("• After first authentication, subsequent runs should be automatic")
    print("• Token cache (token_cache.json) stores refresh tokens securely")

if __name__ == "__main__":
    main()