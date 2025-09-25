# Newsletter Feature Setup Guide

This guide provides step-by-step instructions for setting up the Microsoft Graph API integration for automated newsletter synchronization.

## Overview

The newsletter feature automatically pulls emails from `nyhetsbrev@gronvoldmaskin.no` (folder "Godkjent") via Microsoft Graph API using **delegated permissions** with device code flow. This approach requires one-time authentication by the newsletter account owner but provides better security than application permissions.

## Features

- ✅ **Automated Email Fetching**: Uses Microsoft Graph API with delegated Mail.Read permissions
- ✅ **Device Code Authentication**: One-time setup with automatic token refresh
- ✅ **Security Validation**: Validates sender domain (@gronvoldmaskin.no) and email authentication (SPF/DKIM/DMARC)
- ✅ **HTML Sanitization**: Removes dangerous scripts/content while preserving formatting
- ✅ **Inline Images**: Downloads and serves inline images with CID rewriting
- ✅ **Timezone Support**: Displays times in Europe/Oslo timezone
- ✅ **Token Persistence**: Automatic refresh token management with cache file

## Azure AD Setup

### 1. App Registration (Public Client)

1. Go to [Azure Portal](https://portal.azure.com/) → **Azure Active Directory**
2. Navigate to **App registrations** → **New registration**
3. Fill out the form:
   - **Name**: `IntranettNewslettersDelegated`
   - **Supported account types**: Accounts in this organizational directory only (Single tenant)
   - **Redirect URI**: Select **"Public client/native (mobile & desktop)"** and leave URI empty
4. Click **Register**
5. **Copy and save**:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### 2. Configure as Public Client

1. In your app registration, go to **Authentication**
2. Under **Advanced settings**, set:
   - **Allow public client flows**: **Yes**
   - **Supported account types**: Single tenant only
3. Click **Save**

### 3. API Permissions (Delegated)

1. In your app registration, go to **API permissions**
2. Remove any default permissions (like User.Read if present)
3. Click **Add a permission**
4. Select **Microsoft Graph**
5. Select **Delegated permissions** (NOT Application permissions)
6. Search for and add:
   - `Mail.Read` (Delegated) - *Required: Read user mail*
7. Click **Add permissions**
8. **Note**: No admin consent required for delegated permissions

### 4. Verify Permissions

Your API permissions should show:
```
Microsoft Graph (1)
├── Mail.Read - Delegated - Not granted (this is normal)
```

**Important**: Delegated permissions don't need admin consent and will show "Not granted" until the user (nyhetsbrev@gronvoldmaskin.no) consents during first login.

## Environment Configuration

1. Copy `.env.template` to `.env`:
   ```bash
   cp .env.template .env
   ```

2. Update the following variables in `.env`:

```env
# Newsletter Microsoft Graph API Configuration (DELEGATED PERMISSIONS)
TENANT_ID=your-tenant-id-from-step-1
CLIENT_ID=your-application-client-id-from-step-1

# Graph API Settings for Newsletter (delegated)
GRAPH_SCOPE=Mail.Read
GRAPH_BASE=https://graph.microsoft.com/v1.0

# Newsletter Settings
NEWSLETTER_USER=nyhetsbrev@gronvoldmaskin.no
NEWSLETTER_FOLDER=Godkjent
# Optional: Use explicit folder ID to avoid name resolution (recommended for localized tenants)
# NEWSLETTER_FOLDER_ID=AAMkAGVmMDEzMTM4LTExYjUtNGNkYy05YzY4LTY3YTI3ZmU1YjY2OAAuAAAAAAD7sLojP...
MAX_NEWSLETTERS=10
```

**Note**: No CLIENT_SECRET is needed for delegated permissions with device code flow.

## Email Setup

### 1. Create Newsletter Email Account

1. Ensure `nyhetsbrev@gronvoldmaskin.no` exists in your organization
2. The account needs to be a regular mailbox (not a shared mailbox for Graph API access)

### 2. Create "Godkjent" Folder

1. Log into Outlook with the newsletter account
2. Create a new folder called **"Godkjent"**
3. Set up mail rules to move approved newsletters to this folder

### 3. Prepare Newsletter Account

The newsletter account (nyhetsbrev@gronvoldmaskin.no) needs to:
1. Be accessible for device code authentication
2. Have appropriate credentials available for first-time login
3. Have the "Godkjent" folder created and populated with newsletters

## Folder Resolution (Advanced)

### Using Explicit Folder IDs

For environments with localized folder names or complex folder structures, you can use explicit Microsoft Graph folder IDs instead of folder name resolution. This avoids potential issues with:
- Localized folder names (e.g., "Innboks" instead of "Inbox")
- Special characters in folder names
- Ambiguous folder names in different languages

### Getting Folder IDs

1. **List all folders** to find the correct ID:
   ```bash
   python3 list_folders.py
   ```

2. **Find your target folder** in the output and copy its ID:
   ```
   📁 Godkjent
      ID: AAMkAGVmMDEzMTM4LTExYjUtNGNkYy05YzY4LTY3YTI3ZmU1YjY2OAAuAAAAAAD7sLojP...
   ```

3. **Set the folder ID** in your `.env` file:
   ```env
   NEWSLETTER_FOLDER_ID=AAMkAGVmMDEzMTM4LTExYjUtNGNkYy05YzY4LTY3YTI3ZmU1YjY2OAAuAAAAAAD7sLojP...
   ```

### Folder Resolution Priority

The system uses this priority order:

1. **NEWSLETTER_FOLDER_ID** (if set) - Uses explicit folder ID directly
2. **NEWSLETTER_FOLDER with path** (if contains "/") - Traverses folder path (e.g., "Inbox/Subfolder")
3. **NEWSLETTER_FOLDER name** - Searches all folders by display name

### Path Traversal Examples

You can specify folder paths for nested folders:

```env
# For a folder structure like: Inbox → Project → Newsletters
NEWSLETTER_FOLDER=Inbox/Project/Newsletters

# Or start from any root folder: Sent Items → Archive
NEWSLETTER_FOLDER=Sent Items/Archive
```

**Note**: Path traversal uses case-insensitive matching and will show detailed debug output during folder resolution.

## Installation & Dependencies

1. Install new Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   New dependencies include:
   - `bleach` - HTML sanitization
   - `pytz` - Timezone handling
   - `webencodings` - Character encoding support

2. Initialize/update database schema:
   ```bash
   python main.py
   ```

   This will automatically add new newsletter table columns.

## First-Time Authentication Setup

### 1. Initial Device Code Flow

The first time you try to sync newsletters, you'll see:

```
============================================================
📱 NEWSLETTER AUTHENTICATION REQUIRED
============================================================
Please visit: https://microsoft.com/devicelogin
And enter code: ABCD1234

⚠️  IMPORTANT: Sign in as: nyhetsbrev@gronvoldmaskin.no
This is a one-time setup - future runs will be automatic.
============================================================
```

### 2. Complete Authentication

1. **Open the URL**: Go to https://microsoft.com/devicelogin
2. **Enter the code**: Type the displayed code (e.g., ABCD1234)
3. **Sign in**: Use credentials for `nyhetsbrev@gronvoldmaskin.no`
4. **Grant permissions**: Consent to Mail.Read permission
5. **Verify success**: You should see "Authentication complete" message

### 3. Token Cache Creation

After successful authentication:
- A `token_cache.json` file is created in the project root
- This contains encrypted refresh tokens for automatic renewals
- **Keep this file secure** - it allows access to the newsletter mailbox
- Future synchronizations will be automatic (no user interaction required)

### 4. Token Renewal Process

- Access tokens expire after 1 hour
- Refresh tokens are used automatically to get new access tokens
- Refresh tokens are valid for 90 days by default
- If refresh tokens expire, device code flow will trigger again

## Token Cache Management

A utility script is provided to manage the token cache:

```bash
# Show cache information
python manage_token_cache.py info

# Test authentication (may trigger device code flow)
python manage_token_cache.py test

# Clear cache (forces re-authentication next time)
python manage_token_cache.py clear
```

## Usage

### 1. Access Newsletter Page

- Navigate to `/newsletters` in your intranet
- View list of synchronized newsletters
- Click "Les hele" to view full content

### 2. Manual Synchronization (Admin Only)

1. Go to `/newsletters`
2. Click **"Synkroniser fra e-post"** button
3. Wait for synchronization to complete
4. Check flash messages for results

### 3. Dashboard Integration

- Latest 5 newsletters appear on main dashboard
- Click titles to view full content

## Security Features

### 1. Sender Validation

- Only emails from `@gronvoldmaskin.no` are processed
- Invalid senders are logged and rejected

### 2. Email Authentication

- Checks SPF, DKIM, and DMARC headers when present
- Fails authentication results in rejection

### 3. HTML Sanitization

- Removes `<script>`, `<iframe>`, and dangerous tags
- Sanitizes CSS to prevent XSS attacks
- Allows safe formatting tags (p, h1-h6, strong, em, etc.)

### 4. Content Security

- No user scripts execute from newsletter content
- Images are stored locally and served securely
- CID references rewritten to local URLs

## File Structure

```
app/
├── services/
│   ├── graph_auth.py          # MSAL authentication
│   ├── graph_client.py        # Graph API client
│   ├── newsletter_sanitizer.py # HTML sanitization
│   └── newsletter_ingest.py   # Email processing service
├── templates/
│   └── newsletters/
│       ├── list.html          # Newsletter list page
│       └── detail.html        # Newsletter detail page
└── uploads/
    └── newsletters/           # Inline images storage
```

## Troubleshooting

### Common Issues

1. **"Newsletter service ikke tilgjengelig"**
   - Check that all environment variables are set
   - Verify Python dependencies are installed
   - Check import errors in application logs

2. **Authentication Errors**
   - Verify TENANT_ID, CLIENT_ID, CLIENT_SECRET are correct
   - Ensure admin consent was granted for API permissions
   - Check that Mail.Read permission is present

3. **No Newsletters Found**
   - Verify the "Godkjent" folder exists
   - Check that emails are actually in the folder
   - Confirm NEWSLETTER_USER and NEWSLETTER_FOLDER settings
   - **For localized tenants**: Consider using NEWSLETTER_FOLDER_ID instead of NEWSLETTER_FOLDER

4. **Permission Denied Errors**
   - Ensure the app registration has Mail.Read application permission
   - Verify admin consent was granted
   - Check that the service principal has access to the mailbox

### Debug Mode

Enable debug logging by adding to your code:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Testing Authentication

To test the delegated authentication flow:

```bash
# Run the test script
python test_newsletter.py

# Or test directly by triggering sync
python -c "
from app.services.newsletter_ingest import NewsletterIngestService
service = NewsletterIngestService('database.db')
result = service.sync_newsletters()
print('Sync result:', result)
"
```

**Note**: The first run will trigger device code authentication. Subsequent runs should be automatic.

## Security Best Practices

1. **Secure Token Cache**: Protect `token_cache.json` file with appropriate file permissions
2. **Monitor Usage**: Review API usage in Azure portal
3. **Principle of Least Privilege**: Only use delegated Mail.Read permission
4. **Account Security**: Ensure nyhetsbrev@gronvoldmaskin.no account has strong authentication
5. **Regular Reviews**: Periodically review who has access to the newsletter account
6. **Backup Strategy**: Ensure database backups include newsletter data

### Token Cache Security

```bash
# Set restrictive permissions on token cache
chmod 600 token_cache.json
chown app-user:app-group token_cache.json
```

## Production Deployment

1. **Environment Variables**: Use secure secret management (Azure Key Vault, etc.)
2. **SSL/TLS**: Ensure HTTPS in production
3. **Monitoring**: Set up monitoring for Graph API failures
4. **Rate Limiting**: Graph API has rate limits - monitor usage
5. **High Availability**: Consider caching strategies for newsletter content

## Support

For issues with this feature:
1. Check application logs for detailed error messages
2. Verify Azure AD setup matches this guide exactly
3. Test Graph API access independently
4. Contact IT support with specific error messages and timestamps