# Newsletter Feature Setup Guide

This guide provides step-by-step instructions for setting up the Microsoft Graph API integration for automated newsletter synchronization.

## Overview

The newsletter feature automatically pulls emails from `nyhetsbrev@gronvoldmaskin.no` (folder "Godkjent") via Microsoft Graph API, sanitizes HTML content, stores in the database, and displays the latest 10 newsletters on the intranet dashboard.

## Features

- ✅ **Automated Email Fetching**: Uses Microsoft Graph API with client credentials
- ✅ **Security Validation**: Validates sender domain (@gronvoldmaskin.no) and email authentication (SPF/DKIM/DMARC)
- ✅ **HTML Sanitization**: Removes dangerous scripts/content while preserving formatting
- ✅ **Inline Images**: Downloads and serves inline images with CID rewriting
- ✅ **Timezone Support**: Displays times in Europe/Oslo timezone
- ✅ **Admin Controls**: Admins can trigger manual synchronization

## Azure AD Setup

### 1. App Registration

1. Go to [Azure Portal](https://portal.azure.com/) → **Azure Active Directory**
2. Navigate to **App registrations** → **New registration**
3. Fill out the form:
   - **Name**: `IntranettNewsletters`
   - **Supported account types**: Accounts in this organizational directory only (Single tenant)
   - **Redirect URI**: Leave empty for now
4. Click **Register**
5. **Copy and save**:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### 2. Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description: `Intranet Newsletter Integration`
4. Set expiration: Choose appropriate timeframe (12 months recommended)
5. Click **Add**
6. **Copy and save the secret value immediately** (you won't be able to see it again)

### 3. API Permissions

1. In your app registration, go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Application permissions**
5. Search for and add:
   - `Mail.Read` (Application) - *Required: Read mail in all mailboxes*
6. Click **Add permissions**
7. **Important**: Click **Grant admin consent for [your organization]**
8. Verify the status shows "Granted"

### 4. Verify Permissions

Your API permissions should show:
```
Microsoft Graph (1)
├── Mail.Read - Application - Granted for [Organization]
```

## Environment Configuration

1. Copy `.env.template` to `.env`:
   ```bash
   cp .env.template .env
   ```

2. Update the following variables in `.env`:

```env
# Microsoft Graph API Configuration
TENANT_ID=your-tenant-id-from-step-1
CLIENT_ID=your-application-client-id-from-step-1
CLIENT_SECRET=your-client-secret-from-step-2

# Graph API Settings (usually don't change these)
GRAPH_SCOPE=https://graph.microsoft.com/.default
GRAPH_BASE=https://graph.microsoft.com/v1.0

# Newsletter Settings
NEWSLETTER_USER=nyhetsbrev@gronvoldmaskin.no
NEWSLETTER_FOLDER=Godkjent
MAX_NEWSLETTERS=10
```

## Email Setup

### 1. Create Newsletter Email Account

1. Ensure `nyhetsbrev@gronvoldmaskin.no` exists in your organization
2. The account needs to be a regular mailbox (not a shared mailbox for Graph API access)

### 2. Create "Godkjent" Folder

1. Log into Outlook with the newsletter account
2. Create a new folder called **"Godkjent"**
3. Set up mail rules to move approved newsletters to this folder

### 3. Test Email Access

You can test Graph API access using Graph Explorer:
1. Go to [Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer)
2. Sign in with admin account
3. Try: `GET /users/nyhetsbrev@gronvoldmaskin.no/mailFolders`
4. Verify you can see the "Godkjent" folder

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

### Testing Graph API

Use PowerShell or curl to test API access:

```powershell
# Get access token
$body = @{
    client_id = "your-client-id"
    client_secret = "your-client-secret"
    scope = "https://graph.microsoft.com/.default"
    grant_type = "client_credentials"
}

$response = Invoke-RestMethod -Uri "https://login.microsoftonline.com/your-tenant-id/oauth2/v2.0/token" -Method Post -Body $body
$token = $response.access_token

# Test mailbox access
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/users/nyhetsbrev@gronvoldmaskin.no/mailFolders" -Headers $headers
```

## Security Best Practices

1. **Rotate Secrets**: Regularly rotate the client secret
2. **Monitor Usage**: Review API usage in Azure portal
3. **Principle of Least Privilege**: Only grant necessary permissions
4. **Network Security**: Restrict network egress if possible
5. **Backup Strategy**: Ensure database backups include newsletter data

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