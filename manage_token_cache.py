#!/usr/bin/env python3
"""
Token cache management utility for Newsletter feature.
Use this to manage the token cache for delegated authentication.
"""
import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def show_cache_info():
    """Show information about the current token cache."""
    try:
        from services.graph_auth import GraphAuthManager

        auth_manager = GraphAuthManager()
        cache_info = auth_manager.get_cache_info()

        print("🔍 Token Cache Information")
        print("=" * 40)
        print(f"Cache file exists: {cache_info.get('cache_file_exists', False)}")
        print(f"Accounts in cache: {cache_info.get('accounts_count', 0)}")

        if cache_info.get('accounts'):
            print("\n📧 Cached Accounts:")
            for i, account in enumerate(cache_info['accounts']):
                username = account.get('username', 'Unknown')
                local_id = account.get('local_account_id', 'N/A')
                print(f"  {i+1}. {username} (ID: {local_id})")
        else:
            print("\n⚠️  No cached accounts found")

        if os.path.exists('token_cache.json'):
            import os
            file_size = os.path.getsize('token_cache.json')
            print(f"\nCache file size: {file_size} bytes")

    except Exception as e:
        print(f"❌ Error reading cache info: {e}")

def clear_cache():
    """Clear the token cache."""
    try:
        from services.graph_auth import GraphAuthManager

        auth_manager = GraphAuthManager()
        auth_manager.clear_cache()
        print("✅ Token cache cleared successfully")
        print("Next newsletter sync will require device code authentication")

    except Exception as e:
        print(f"❌ Error clearing cache: {e}")

def test_auth():
    """Test authentication (may trigger device code flow)."""
    try:
        from services.graph_auth import GraphAuthManager

        print("🔐 Testing Authentication...")
        print("⚠️  This may trigger device code flow if no valid tokens exist")

        auth_manager = GraphAuthManager()
        token = auth_manager.get_token()

        if token:
            print("✅ Successfully acquired access token")
            print(f"Token length: {len(token)} characters")
            print(f"Token preview: {token[:20]}...")
        else:
            print("❌ Failed to acquire access token")

    except Exception as e:
        print(f"❌ Authentication error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage Newsletter token cache")
    parser.add_argument('action', choices=['info', 'clear', 'test'],
                       help='Action to perform: info (show cache info), clear (clear cache), test (test auth)')

    args = parser.parse_args()

    print("🚀 Newsletter Token Cache Manager")
    print("=" * 50)

    if args.action == 'info':
        show_cache_info()
    elif args.action == 'clear':
        confirm = input("Are you sure you want to clear the token cache? (y/N): ")
        if confirm.lower() == 'y':
            clear_cache()
        else:
            print("❌ Cache clear cancelled")
    elif args.action == 'test':
        test_auth()

if __name__ == "__main__":
    main()