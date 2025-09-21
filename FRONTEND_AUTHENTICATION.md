# Frontend Authentication Integration

This document explains how the frontend integrates with the Microsoft Entra ID authentication backend.

## Authentication Flow Overview

### 1. **Login Process**
```
User clicks "Login" → Redirects to Microsoft → User authenticates → Callback sets session cookie → Frontend detects login
```

**Detailed Steps:**
1. User visits any page of the intranet
2. JavaScript calls `fetch('/api/me')` to check authentication status
3. If user is not logged in (401 response), show login button
4. User clicks "Login with Office 365" → redirects to `/auth/login`
5. Backend redirects to Microsoft Entra ID login page
6. User authenticates with their Office 365 credentials
7. Microsoft redirects back to `/auth/callback` with authorization code
8. Backend exchanges code for tokens, creates session, and redirects to frontend
9. Frontend JavaScript detects authentication and shows the navbar

### 2. **Session Management**
- **Session Storage**: Server-side sessions with secure HTTP-only cookies
- **Session Check**: Frontend calls `/api/me` on every page load
- **Session Persistence**: Sessions persist across browser restarts (until logout or expiry)

### 3. **Logout Process**
```
User clicks "Logout" → JavaScript calls POST /auth/logout → Session cleared → Page reloads → Shows login screen
```

**Detailed Steps:**
1. User clicks "Logg ut" in the dropdown menu
2. JavaScript `logout()` function calls `POST /auth/logout`
3. Backend clears the session and provides Microsoft logout URL
4. Page reloads automatically
5. JavaScript auth check fails → shows login screen

## Frontend Components

### `templates/base.html`
```html
<!-- Two main sections that toggle based on authentication status -->

<!-- Login Section (hidden when authenticated) -->
<div id="login-section" class="login-container">
    <a href="http://localhost:5050/auth/login" class="login-btn">
        Login with Office 365
    </a>
</div>

<!-- Navigation Bar (hidden when not authenticated) -->
<nav id="topbar" class="topbar">
    <div id="user-info">
        <span id="user-name">User Name</span>
        <!-- Logout button calls logout() function -->
        <a href="#" onclick="logout()">Logg ut</a>
    </div>
</nav>
```

### `static/js/main.js`
```javascript
// Authentication check on page load
async function checkAuthentication() {
    const response = await fetch('http://localhost:5050/api/me', {
        credentials: 'include'  // Important: includes session cookies
    });

    if (response.ok) {
        const userData = await response.json();
        showAuthenticatedUI(userData);
    } else {
        showLoginUI();
    }
}

// Logout function
async function logout() {
    await fetch('http://localhost:5050/auth/logout', {
        method: 'POST',
        credentials: 'include'
    });
    window.location.reload();
}
```

## API Endpoints Used by Frontend

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/me` | GET | Check authentication status | `200: user data` or `401: unauthorized` |
| `/auth/login` | GET | Start login flow | Redirects to Microsoft |
| `/auth/logout` | POST | End session | `200: success` + logout URL |

### Example `/api/me` Response
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

## Key Features

### ✅ **Automatic Authentication Detection**
- Every page load checks authentication status
- No manual login state management required
- Seamless transition between logged-in and logged-out states

### ✅ **Admin Role Support**
- Frontend automatically shows/hides admin navigation based on `is_admin` field
- No hardcoded user permissions in frontend

### ✅ **Session Security**
- Sessions are HTTP-only cookies (cannot be accessed by JavaScript)
- CSRF protection via state parameter in OAuth flow
- Automatic session expiry and refresh

### ✅ **Cross-Origin Support**
- Backend runs on port 5050, frontend can run on different port
- Proper CORS headers configured
- `credentials: 'include'` ensures cookies are sent cross-origin

## Development Notes

### **CORS Configuration**
The backend is configured to accept requests from the frontend:
```python
# In backend/app.py
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', Config.BASE_URL)
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response
```

### **Testing Authentication**
1. **Test Login**: Visit any page → should see login button → click → redirects to Microsoft
2. **Test Session**: After login, refresh page → should stay logged in
3. **Test Logout**: Click logout → should show login screen again
4. **Test Admin**: Login with admin account → should see admin navigation

### **Troubleshooting**

**Problem**: "Login button doesn't work"
- Check backend is running on http://localhost:5050
- Check browser console for CORS errors

**Problem**: "Always shows login screen"
- Check `/api/me` endpoint returns 200 with user data
- Check browser cookies are being set
- Verify `credentials: 'include'` is in fetch calls

**Problem**: "Logout doesn't work"
- Check POST to `/auth/logout` returns 200
- Verify page reloads after logout call
- Check session cookie is cleared in browser

## Security Considerations

- ✅ **No tokens in localStorage**: All authentication handled via secure HTTP-only cookies
- ✅ **No sensitive data in frontend**: User data fetched fresh on each page load
- ✅ **CSRF protection**: State parameter validates OAuth flow
- ✅ **Session timeout**: Backend handles session expiry automatically

The frontend is stateless and relies entirely on the backend for authentication state, making it secure and simple to maintain.