# GRM Intranett Authentication Setup

This document explains how to run the GRM Intranett with Microsoft Entra ID (Office 365) authentication.

## Architecture Overview

The application consists of two Flask services:

1. **Authentication Backend** (Port 5050): Handles Microsoft OAuth and session management
2. **Main Intranet App** (Port 5000): Serves templates, static files, and business logic

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Browser  │    │  Main App :5000  │    │ Auth Backend    │
│                 │◄──►│                  │◄──►│     :5050       │
│                 │    │ Templates/Static │    │ Microsoft OAuth │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## How Authentication Works

### 1. **Login Flow**
```
1. User visits http://localhost:5000
2. Main app calls auth backend /api/me to check session
3. If not authenticated: main app redirects to auth backend /auth/login
4. Auth backend redirects to Microsoft Entra ID login
5. User authenticates with Office 365 credentials
6. Microsoft redirects back to auth backend /auth/callback
7. Auth backend sets session cookie and redirects to main app
8. Main app shows navbar with user info
```

### 2. **Session Management**
- **Server-side sessions**: Secure HTTP-only cookies, no localStorage
- **Cross-service**: Main app passes cookies to auth backend via `requests`
- **User data**: Fetched fresh from auth backend `/api/me` on each request

### 3. **Logout Flow**
```
1. User clicks "Logg ut" in navbar
2. JavaScript calls auth backend /auth/logout (POST)
3. Auth backend clears session
4. User redirected to login screen
```

## Starting the Applications

### Prerequisites
- Python 3.8+
- Microsoft 365 tenant with App Registration configured
- Both applications configured with environment variables

### Step 1: Start Authentication Backend
```bash
# Navigate to project root
cd /path/to/intranett_grm

# Start authentication backend (port 5050)
python intranet/backend/app.py
```

**Expected output:**
```
Starting intranet authentication service...
Base URL: http://localhost:5050
Running on port: 5050
Session type: filesystem
Admin users: 1 configured
* Running on http://127.0.0.1:5050
```

### Step 2: Start Main Intranet App
```bash
# In a new terminal, same project directory
cd /path/to/intranett_grm

# Start main application (port 5000)
python app.py
```

**Expected output:**
```
* Running on http://127.0.0.1:5000
* Debug mode: on
```

### Step 3: Access the Application
1. Open browser and visit `http://localhost:5000`
2. You should see the Office 365 login screen
3. Click "Logg inn med Office 365"
4. Authenticate with your Office 365 account
5. After successful login, you'll see the intranet dashboard

## Code Architecture

### Main App (app.py)
```python
# Authentication helper
def get_current_user():
    \"\"\"Get user from auth backend using session cookies\"\"\"
    response = requests.get(
        'http://localhost:5050/api/me',
        cookies=request.cookies  # Pass session cookies
    )
    return response.json() if response.status_code == 200 else None

# Authentication decorator
@auth_required
def dashboard():
    user = get_current_user()  # Get fresh user data
    return render_template('dashboard.html', user=user)
```

### Templates (base.html)
```html
<!-- Server-side rendering based on user data -->
{% if not user %}
    <!-- Show login button -->
    <a href="http://localhost:5050/auth/login">Login with Office 365</a>
{% else %}
    <!-- Show navbar with user info -->
    <span>{{ user.displayName or user.mail }}</span>
    {% if user.is_admin %}
        <!-- Show admin navigation -->
    {% endif %}
{% endif %}
```

### JavaScript (main.js)
```javascript
// Simple logout function
async function logoutUser() {
    await fetch('http://localhost:5050/auth/logout', {
        method: 'POST',
        credentials: 'include'
    });
    window.location.href = '/';
}
```

## API Endpoints

### Authentication Backend (Port 5050)
| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/auth/login` | GET | Start OAuth flow | Redirect to Microsoft |
| `/auth/callback` | GET | Handle OAuth callback | Redirect to main app |
| `/api/me` | GET | Get current user | User JSON or 401 |
| `/auth/logout` | POST | Clear session | Success message |

### Main App (Port 5000)
| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/` | GET | Home (redirect to dashboard) | No (redirects to login) |
| `/dashboard` | GET | Main dashboard | Yes |
| `/documents` | GET | Document management | Yes |
| `/calendar` | GET | Calendar view | Yes |
| `/tasks` | GET | Task management | Yes |
| `/suppliers` | GET | Supplier passwords | Yes |
| `/newsletter` | GET | Newsletter management | Yes (admin for create) |

## User Data Structure

When authenticated, the user object contains:
```json
{
  "id": "uuid",
  "displayName": "John Doe",
  "givenName": "John",
  "surname": "Doe",
  "mail": "john.doe@company.com",
  "userPrincipalName": "john.doe@company.com",
  "jobTitle": "Software Engineer",
  "department": "IT",
  "is_admin": false
}
```

## Security Features

### ✅ **What's Implemented**
- **HTTP-only session cookies**: Cannot be accessed by JavaScript
- **CSRF protection**: State parameter in OAuth flow
- **Secure session storage**: Server-side filesystem sessions
- **Admin role checking**: Based on UPN in ADMIN_UPNS environment variable
- **Token refresh**: Automatic refresh of Microsoft Graph tokens
- **Minimal scopes**: Only requests User.Read from Microsoft Graph

### ✅ **Best Practices Followed**
- No tokens stored in localStorage or client-side
- Fresh user data fetched on each request
- Proper error handling for authentication failures
- CORS configured for cross-origin cookie support
- Session timeout handled gracefully

## Troubleshooting

### **Problem**: "Cannot connect to authentication backend"
**Solution**:
1. Ensure auth backend is running on port 5050
2. Check firewall settings
3. Verify `AUTH_BACKEND_URL` in main app

### **Problem**: "Always redirects to login"
**Solution**:
1. Check auth backend `/api/me` returns 200 with user data
2. Verify session cookies are being set
3. Check browser developer tools for cookie issues
4. Ensure both apps are on same domain (localhost)

### **Problem**: "Admin features not showing"
**Solution**:
1. Check user UPN is in `ADMIN_UPNS` environment variable in auth backend
2. Verify `user.is_admin` is true in `/api/me` response
3. Check template logic: `{% if user.is_admin %}`

### **Problem**: "CORS errors"
**Solution**:
1. Verify `APP_BASE_URL` matches frontend URL
2. Check CORS headers in auth backend responses
3. Ensure `credentials: 'include'` in JavaScript fetch calls

## Development vs Production

### **Development Setup** (Current)
- Auth backend: `http://localhost:5050`
- Main app: `http://localhost:5000`
- Session storage: Filesystem
- HTTPS: Not required for localhost

### **Production Considerations**
- Use HTTPS for both services
- Redis for session storage (shared between instances)
- Load balancer with session affinity
- Environment variables for all configuration
- Separate domains/subdomains if needed

## Environment Variables

Both applications need proper environment variables configured. See the respective `.env.example` files for details.

**Key variables:**
- `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`: Azure App Registration
- `ADMIN_UPNS`: Comma-separated list of admin user emails
- `APP_BASE_URL`: Main application URL
- `SESSION_TYPE`: `filesystem` for dev, `redis` for production

This setup provides secure, scalable authentication while keeping the architecture simple and maintainable.