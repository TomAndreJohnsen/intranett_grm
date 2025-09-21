# GRM Intranet - Unified Application

This document explains how to run the unified GRM Intranet application with integrated Microsoft Entra ID authentication.

## Overview

The application has been **unified** into a single Flask process that combines:
- **Microsoft Entra ID authentication** (OAuth2/OIDC with MSAL)
- **Main intranet functionality** (dashboard, documents, calendar, tasks, etc.)
- **Session management** with Flask-Session
- **Static files and templates** serving

**Everything runs on one port: `http://localhost:5000`**

## Quick Start

### 1. Install Dependencies
```bash
pip install flask flask-session msal requests python-dotenv werkzeug
```

### 2. Configure Environment Variables
Create a `.env` file in the project root with the following variables:

```bash
# Flask Configuration
FLASK_SECRET_KEY=your-very-long-random-secret-key-change-this-in-production

# Microsoft Entra ID Configuration
MS_CLIENT_ID=your-azure-app-client-id
MS_CLIENT_SECRET=your-azure-app-client-secret
MS_TENANT_ID=your-azure-tenant-id

# Application Configuration
APP_BASE_URL=http://localhost:5000

# Admin Users (comma-separated UPNs)
ADMIN_UPNS=admin@company.com,manager@company.com

# Session Configuration
SESSION_TYPE=filesystem
```

### 3. Azure App Registration Setup
1. Go to [Azure Portal](https://portal.azure.com) → **Azure Active Directory** → **App registrations**
2. Create new registration:
   - **Name**: `GRM Intranet`
   - **Redirect URI**: `http://localhost:5000/auth/callback`
3. Copy **Application (client) ID** → `MS_CLIENT_ID`
4. Copy **Directory (tenant) ID** → `MS_TENANT_ID`
5. Create client secret → copy value → `MS_CLIENT_SECRET`
6. Set API permissions: `User.Read` (Microsoft Graph)

### 4. Run the Application
```bash
python app.py
```

**Expected output:**
```
Starting GRM Intranet with integrated authentication...
Base URL: http://localhost:5000
Session type: filesystem
Admin users: 2 configured
* Running on http://0.0.0.0:5000
```

### 5. Access the Application
1. Open browser: `http://localhost:5000`
2. Click "Logg inn med Office 365"
3. Authenticate with your Microsoft account
4. Access the intranet dashboard

## Authentication Flow

### Login Process
```
1. User visits http://localhost:5000
2. If not authenticated → shows Office 365 login button
3. User clicks login → redirects to /auth/login
4. App redirects to Microsoft Entra ID
5. User authenticates with Office 365
6. Microsoft redirects to /auth/callback
7. App processes tokens, stores user in session
8. User redirected to dashboard with session cookie
```

### Session Management
- **Storage**: Server-side sessions (filesystem by default)
- **Security**: HTTP-only cookies, CSRF protection via state parameter
- **Persistence**: Sessions survive browser restarts until logout

### Logout Process
```
1. User clicks "Logg ut" → JavaScript calls /auth/logout
2. App clears session and returns Microsoft logout URL
3. User redirected to Microsoft logout
4. Microsoft redirects back to app homepage
```

## API Endpoints

### Authentication Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | GET | Start Microsoft OAuth flow |
| `/auth/callback` | GET | Handle OAuth callback |
| `/auth/logout` | POST | Clear session and logout |

### User API
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/me` | GET | Get current user JSON |
| `/api/healthz` | GET | Health check |

### Main Application Routes
| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/` | GET | Home (redirect to dashboard) | No |
| `/dashboard` | GET | Main dashboard | Yes |
| `/documents` | GET | Document management | Yes |
| `/calendar` | GET | Calendar | Yes |
| `/tasks` | GET | Task management | Yes |
| `/suppliers` | GET | Supplier passwords | Yes |
| `/newsletter` | GET | Newsletter (admin: create) | Yes |

## Example API Responses

### `/api/me` - Current User
```json
{
  "id": "12345678-1234-1234-1234-123456789012",
  "displayName": "John Doe",
  "givenName": "John",
  "surname": "Doe",
  "userPrincipalName": "john.doe@company.com",
  "mail": "john.doe@company.com",
  "jobTitle": "Software Engineer",
  "department": "IT",
  "is_admin": false
}
```

### `/api/healthz` - Health Check
```json
{
  "status": "ok",
  "service": "intranet-unified",
  "authenticated": true
}
```

## Environment Variables Reference

### Required Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Flask session encryption key | `your-64-char-random-string` |
| `MS_CLIENT_ID` | Azure App Registration Client ID | `12345678-1234-1234-1234-123456789012` |
| `MS_CLIENT_SECRET` | Azure App Registration Client Secret | `abcdef123456...` |
| `MS_TENANT_ID` | Azure Tenant ID | `87654321-4321-4321-4321-210987654321` |

### Optional Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `APP_BASE_URL` | Application base URL | `http://localhost:5000` |
| `ADMIN_UPNS` | Comma-separated admin emails | (empty) |
| `SESSION_TYPE` | Session storage type | `filesystem` |
| `SESSION_KEY_PREFIX` | Session key prefix | `intranet:` |
| `REDIS_URL` | Redis URL (if SESSION_TYPE=redis) | (none) |

### Generating Secure Secret Key
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Template Integration

The unified app uses server-side rendering with user context:

```html
<!-- templates/base.html -->
{% if not user %}
    <!-- Show login button -->
    <a href="/auth/login" class="login-btn">
        Login with Office 365
    </a>
{% else %}
    <!-- Show authenticated navigation -->
    <nav class="topbar">
        <span class="user-name">{{ user.displayName or user.mail }}</span>
        {% if user.is_admin %}
            <!-- Show admin navigation -->
        {% endif %}
        <a href="#" onclick="logoutUser()">Logout</a>
    </nav>
{% endif %}
```

## JavaScript Integration

Simple logout function that calls the unified app:

```javascript
// static/js/main.js
async function logoutUser() {
    const response = await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
        const data = await response.json();
        if (data.logout_url) {
            window.location.href = data.logout_url;
            return;
        }
    }

    window.location.href = '/';
}
```

## Development vs Production

### Development (Current Setup)
- Port: `5000`
- Session: `filesystem`
- HTTPS: Not required for localhost
- Secret: Can use default for testing

### Production Considerations
- **HTTPS**: Required for secure cookies
- **Session**: Use `redis` for scalability
- **Secret**: Generate secure `FLASK_SECRET_KEY`
- **Environment**: Set `SESSION_COOKIE_SECURE=true`
- **Domain**: Update `APP_BASE_URL` and Azure redirect URI

### Production Environment Variables
```bash
FLASK_SECRET_KEY=your-production-secret-key
APP_BASE_URL=https://intranet.company.com
SESSION_TYPE=redis
REDIS_URL=redis://your-redis-server:6379/0
SESSION_COOKIE_SECURE=true
```

## Troubleshooting

### Common Issues

**❌ "Missing required environment variables"**
- Check `.env` file exists and has all MS_* variables
- Verify environment variables are loaded correctly

**❌ "Authentication failed"**
- Verify Azure App Registration redirect URI matches exactly
- Check client secret hasn't expired
- Ensure API permissions are granted

**❌ "AADSTS50011: Reply URL mismatch"**
- Azure redirect URI must be: `http://localhost:5000/auth/callback`
- Check `APP_BASE_URL` environment variable

**❌ "Admin features not showing"**
- Check user UPN is in `ADMIN_UPNS` environment variable
- Verify user object has `is_admin: true` in `/api/me`

### Debug Tips
1. Check Flask console output for configuration errors
2. Visit `/api/me` to see current user JSON
3. Check browser developer tools for session cookies
4. Verify `/api/healthz` returns `authenticated: true`

## Key Benefits of Unified App

- ✅ **Single process**: Only one app to run and manage
- ✅ **Shared sessions**: Frontend and backend use same session
- ✅ **No CORS issues**: All requests are same-origin
- ✅ **Simplified deployment**: One app, one port, one configuration
- ✅ **Integrated authentication**: No separate auth service needed
- ✅ **Better performance**: No cross-service HTTP calls

The unified architecture provides a simpler, more maintainable solution while preserving all authentication security features and business functionality.