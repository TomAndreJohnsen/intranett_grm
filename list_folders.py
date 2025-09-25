import os
import msal
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
SCOPES = ["Mail.Read"]

# Validate required environment variables
if not TENANT_ID or not CLIENT_ID:
    print("❌ Missing TENANT_ID or CLIENT_ID in .env")
    print("Please ensure .env file contains:")
    print("  TENANT_ID=your-tenant-id")
    print("  CLIENT_ID=your-client-id")
    exit(1)

# Debug: Print environment variables (masked for security)
print("🔧 Microsoft Graph Mail Folders Listing")
print("=" * 50)
print(f"📧 Tenant ID: {TENANT_ID[:8]}...{TENANT_ID[-4:]}")
print(f"🆔 Client ID: {CLIENT_ID[:8]}...{CLIENT_ID[-4:]}")
print(f"🔑 Scopes: {', '.join(SCOPES)}")
print()

cache = msal.SerializableTokenCache()
if os.path.exists("token_cache.json"):
    cache.deserialize(open("token_cache.json", "r").read())

app = msal.PublicClientApplication(CLIENT_ID, authority=f"https://login.microsoftonline.com/{TENANT_ID}", token_cache=cache)

accounts = app.get_accounts()
if not accounts:
    print("❌ No accounts in token cache. Run manage_token_cache.py first.")
    exit(1)

result = app.acquire_token_silent(SCOPES, account=accounts[0])
if not result:
    print("❌ No token found.")
    exit(1)

headers = {"Authorization": f"Bearer {result['access_token']}"}

print("📁 Fetching mail folders...")
url = "https://graph.microsoft.com/v1.0/me/mailFolders?$expand=childFolders"
resp = requests.get(url, headers=headers)

if resp.status_code != 200:
    print(f"❌ API request failed: {resp.status_code}")
    print(f"Response: {resp.text}")
    exit(1)

data = resp.json()

print("✅ Mail folders retrieved successfully")
print("\n📂 Mail Folders:")
print("=" * 60)

def print_folder(folder, indent=0):
    """Print folder information with proper indentation."""
    prefix = "  " * indent
    display_name = folder.get('displayName', 'Unknown')
    folder_id = folder.get('id', 'No ID')

    print(f"{prefix}📁 {display_name}")
    print(f"{prefix}   ID: {folder_id}")

    # Print child folders if they exist
    child_folders = folder.get('childFolders', [])
    if child_folders:
        for child in child_folders:
            print_folder(child, indent + 1)

# Print all folders
if 'value' in data:
    for folder in data['value']:
        print_folder(folder)
        print()  # Empty line between top-level folders
else:
    print("❌ No folders found in response")
    print("Raw response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))