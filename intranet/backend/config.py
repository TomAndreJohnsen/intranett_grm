"""
Configuration management for Microsoft Entra ID authentication.
Handles environment variables and application settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class."""

    # Flask configuration - ensure SECRET_KEY is always a string
    SECRET_KEY = str(os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production'))

    # Microsoft Entra ID configuration
    CLIENT_ID = os.environ.get('MS_CLIENT_ID')
    CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET')
    TENANT_ID = os.environ.get('MS_TENANT_ID')

    # Application configuration
    BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    REDIRECT_URI = f"{BASE_URL}/auth/callback"

    # Admin users (comma-separated UPNs)
    ADMIN_UPNS = [upn.strip() for upn in os.environ.get('ADMIN_UPNS', '').split(',') if upn.strip()]

    # Session configuration - ensure all values are proper types
    SESSION_TYPE = str(os.environ.get('SESSION_TYPE', 'filesystem'))
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = str(os.environ.get('SESSION_KEY_PREFIX', 'intranet:'))
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = str(os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'))
    SESSION_COOKIE_NAME = str(os.environ.get('SESSION_COOKIE_NAME', 'session'))
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')  # None for localhost
    SESSION_COOKIE_PATH = str(os.environ.get('SESSION_COOKIE_PATH', '/'))
    SESSION_FILE_THRESHOLD = int(os.environ.get('SESSION_FILE_THRESHOLD', 500))

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
        """Validate that all required configuration is present and properly typed."""
        # Check required MS variables
        required_vars = ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID']
        missing_vars = []

        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(f'MS_{var}')

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Validate SECRET_KEY
        if not cls.SECRET_KEY or cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError("FLASK_SECRET_KEY must be set to a secure random string in production")

        if not isinstance(cls.SECRET_KEY, str):
            raise TypeError(f"FLASK_SECRET_KEY must be a string, got {type(cls.SECRET_KEY)}")

        if len(cls.SECRET_KEY) < 32:
            raise ValueError("FLASK_SECRET_KEY should be at least 32 characters long")

        return True