# Intranet Microsoft Entra ID Authentication

Secure Microsoft Entra ID (Azure AD / Office 365) authentication backend for the company intranet. This backend provides authentication endpoints and user API that the existing frontend can integrate with.

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Microsoft 365 tenant
- Azure App Registration (see setup instructions below)

### Local Development Setup

1. **Clone and navigate to the project:**
   ```bash
   cd intranet/backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp ../.env.example ../.env
   # Edit .env with your Azure App Registration details
   ```

5. **Run the development server:**
   ```bash
   python app.py
   ```

The authentication service will be available at `http://localhost:5000`

## 🔧 Azure App Registration Setup

### Step 1: Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Fill out the form:
   - **Name**: `Company Intranet`
   - **Supported account types**: `Accounts in this organizational directory only`
   - **Redirect URI**:
     - Type: `Web`
     - URL: `http://localhost:5000/auth/callback`
5. Click **Register**

### Step 2: Configure Authentication

1. In your new app registration, go to **Authentication**
2. Under **Redirect URIs**, ensure you have:
   - `http://localhost:5000/auth/callback` (for development)
3. Under **Implicit grant and hybrid flows**, check:
   - ✅ **ID tokens**
4. Click **Save**

### Step 3: Generate Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: `Intranet Backend Secret`
4. Set expiration: `24 months` (recommended)
5. Click **Add**
6. **⚠️ Copy the secret value immediately** - you won't be able to see it again

### Step 4: Configure API Permissions

1. Go to **API permissions**
2. Ensure you have these Microsoft Graph permissions:
   - `User.Read` (should be added by default)
   - `openid`
   - `profile`
   - `email`
3. Click **Grant admin consent** if required

### Step 5: Get Your Configuration Values

Copy these values to your `.env` file:

- **Application (client) ID** → `MS_CLIENT_ID`
- **Directory (tenant) ID** → `MS_TENANT_ID`
- **Client secret value** → `MS_CLIENT_SECRET`

## 📁 Project Structure

```
intranet/
├── backend/
│   ├── app.py              # Main Flask application
│   ├── auth.py             # Authentication logic with MSAL
│   ├── config.py           # Configuration management
│   ├── wsgi.py             # WSGI entry point for production
│   └── requirements.txt    # Python dependencies
├── .env.example            # Environment variables template
└── README.md               # This file
```

## 🔌 API Endpoints

### Authentication Endpoints

- **`GET /auth/login`** - Initiate Microsoft login flow
- **`GET /auth/callback`** - Handle OAuth callback from Microsoft
- **`POST /auth/logout`** - Log out current user

### API Endpoints

- **`GET /api/me`** - Get current user information
- **`GET /api/healthz`** - Health check endpoint

### Example API Response (`/api/me`)

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

## 🔐 Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Flask session encryption key | `your-very-long-random-secret-key` |
| `MS_CLIENT_ID` | Azure App Registration Client ID | `12345678-1234-1234-1234-123456789012` |
| `MS_CLIENT_SECRET` | Azure App Registration Client Secret | `abcdef123456...` |
| `MS_TENANT_ID` | Azure Tenant ID | `87654321-4321-4321-4321-210987654321` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_BASE_URL` | Application base URL | `http://localhost:5000` |
| `ADMIN_UPNS` | Comma-separated admin user emails | `admin@grm.no` |
| `SESSION_TYPE` | Session storage type | `filesystem` |
| `REDIS_URL` | Redis connection URL (if using Redis) | None |

## 🚀 Production Deployment

### Step 1: Update Azure App Registration

1. In Azure Portal, go to your App Registration
2. Navigate to **Authentication**
3. Add your production redirect URI:
   - `https://your-domain.com/auth/callback`
4. Click **Save**

### Step 2: Update Environment Variables

Update your production `.env` file:

```bash
# Production configuration
APP_BASE_URL=https://your-domain.com
SESSION_TYPE=redis
REDIS_URL=redis://your-redis-server:6379/0

# Generate a new, secure secret key
FLASK_SECRET_KEY=your-new-production-secret-key-make-it-very-long-and-random

# Keep your Azure credentials the same
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret
MS_TENANT_ID=your-tenant-id

# Update admin users for your organization
ADMIN_UPNS=admin@company.com,manager@company.com
```

### Step 3: Deploy with Gunicorn

```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 wsgi:app
```

### Step 4: Set up HTTPS

**⚠️ Important**: Always use HTTPS in production to protect authentication tokens and session cookies.

- Use a reverse proxy (nginx, Apache) with SSL certificate
- Or deploy behind a cloud load balancer with SSL termination

## 🔒 Security Best Practices

### ✅ What This Implementation Does

- **Secure token storage**: Tokens stored in server-side sessions
- **CSRF protection**: State parameter validates OAuth flow
- **Minimal scopes**: Only requests necessary Graph API permissions
- **Admin role checking**: UPN-based admin privilege assignment
- **Token refresh**: Automatic token refresh when possible
- **Secure session cookies**: HTTPOnly and secure flags in production

### ⚠️ Security Considerations

1. **Never commit secrets**: Keep `.env` files out of version control
2. **Use HTTPS in production**: Required for secure cookie transmission
3. **Generate strong secret keys**: Use long, random strings for `FLASK_SECRET_KEY`
4. **Regularly rotate secrets**: Update client secrets and session keys
5. **Use Redis in production**: Filesystem sessions don't scale and are less secure
6. **Keep dependencies updated**: Regularly update Python packages

### 🔑 Generating Secure Secret Keys

```python
# Generate a secure secret key
import secrets
print(secrets.token_urlsafe(64))
```

## 🔧 Troubleshooting

### Common Issues

**❌ "Missing required environment variables"**
- Check that all required variables are set in `.env`
- Verify `.env` file is in the correct location (`intranet/.env`)

**❌ "AADSTS50011: The reply URL specified in the request does not match"**
- Verify redirect URI in Azure matches exactly: `http://localhost:5000/auth/callback`
- Check that `APP_BASE_URL` is correctly set

**❌ "Authentication failed"**
- Verify client secret is copied correctly from Azure
- Check that tenant ID is correct
- Ensure API permissions are granted in Azure

**❌ "CORS errors in browser"**
- Check that `APP_BASE_URL` matches your frontend URL
- Verify CORS headers are properly configured

### Debug Mode

Enable debug logging by setting:

```bash
export FLASK_DEBUG=1
```

## 🔄 Local to Production Migration Checklist

- [ ] **Azure Configuration**
  - [ ] Add production redirect URI to Azure App Registration
  - [ ] Verify API permissions are granted
  - [ ] Note client secret expiration date

- [ ] **Environment Setup**
  - [ ] Update `APP_BASE_URL` to production domain
  - [ ] Change `SESSION_TYPE` to `redis`
  - [ ] Set up Redis server and update `REDIS_URL`
  - [ ] Generate new `FLASK_SECRET_KEY` for production
  - [ ] Update `ADMIN_UPNS` with production admin emails

- [ ] **Infrastructure**
  - [ ] Set up HTTPS/SSL certificates
  - [ ] Configure reverse proxy (nginx/Apache)
  - [ ] Set up Redis server
  - [ ] Configure firewall rules

- [ ] **Deployment**
  - [ ] Install dependencies: `pip install -r requirements.txt`
  - [ ] Deploy with production WSGI server (Gunicorn)
  - [ ] Test authentication flow end-to-end
  - [ ] Verify admin privileges work correctly

- [ ] **Security**
  - [ ] Verify HTTPS is enforced
  - [ ] Test that secrets are not exposed
  - [ ] Confirm session cookies are secure
  - [ ] Review and update security headers

## 📞 Support

For issues with this authentication backend:

1. Check the troubleshooting section above
2. Verify Azure App Registration configuration
3. Review application logs for detailed error messages
4. Ensure all environment variables are properly set

For Microsoft Entra ID and Azure configuration issues, consult the [official Microsoft documentation](https://docs.microsoft.com/en-us/azure/active-directory/).