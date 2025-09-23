"""
Configuration management for Microsoft Entra ID authentication.
Handles environment variables and application settings.
"""
import os
from dotenv import load_dotenv
from flask import request

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class."""

    # Flask configuration
    SECRET_KEY = str(os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production'))

    # Microsoft Entra ID configuration
    CLIENT_ID = os.environ.get('MS_CLIENT_ID')
    CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET')
    TENANT_ID = os.environ.get('MS_TENANT_ID')

    # Application configuration
    BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    REDIRECT_URI = f"{BASE_URL}/auth/callback"

    @classmethod
    def get_redirect_uri(cls):
        """
        Get the redirect URI dynamically based on the current request.
        Supports both localhost and IP address configurations.
        """
        try:
            # Try to get the current request host
            if request and hasattr(request, 'host'):
                host = request.host
                scheme = request.scheme

                # Build dynamic redirect URI
                redirect_uri = f"{scheme}://{host}/auth/callback"
                return redirect_uri
        except RuntimeError:
            # Outside of request context, fall back to configured URI
            pass

        # Fallback to configured redirect URI
        return cls.REDIRECT_URI

    # Admin users (comma-separated UPNs)
    ADMIN_UPNS = [upn.strip() for upn in os.environ.get('ADMIN_UPNS', '').split(',') if upn.strip()]

    # Session configuration
    SESSION_TYPE = str(os.environ.get('SESSION_TYPE', 'filesystem'))
    SESSION_PERMANENT = True  # Enable permanent sessions
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = str(os.environ.get('SESSION_KEY_PREFIX', 'intranet:'))
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = str(os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'))
    SESSION_COOKIE_NAME = str(os.environ.get('SESSION_COOKIE_NAME', 'session'))
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')  # None for localhost
    SESSION_COOKIE_PATH = str(os.environ.get('SESSION_COOKIE_PATH', '/'))
    SESSION_FILE_THRESHOLD = int(os.environ.get('SESSION_FILE_THRESHOLD', 500))

    # Session file directory (for filesystem sessions)
    SESSION_FILE_DIR = os.path.join(os.getcwd(), 'flask_session')

    @classmethod
    def ensure_session_dir(cls):
        """Ensure the session directory exists."""
        if not os.path.exists(cls.SESSION_FILE_DIR):
            os.makedirs(cls.SESSION_FILE_DIR, exist_ok=True)

    # Redis configuration (optional)
    REDIS_URL = os.environ.get('REDIS_URL')
    if SESSION_TYPE == 'redis' and REDIS_URL:
        SESSION_REDIS = REDIS_URL

    # Microsoft Graph API scopes
    SCOPES = [
        "https://graph.microsoft.com/User.Read"
    ]

    # Microsoft endpoints
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present."""
        # Check required MS variables
        required_vars = ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID']
        missing_vars = []

        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(f'MS_{var}')

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True