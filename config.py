import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FLASK_SECRET_KEY must be set in environment variables")

    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'database.db')

    # Microsoft Entra ID
    MS_CLIENT_ID = os.environ.get('MS_CLIENT_ID')
    MS_CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET')
    MS_TENANT_ID = os.environ.get('MS_TENANT_ID')

    # Application settings
    BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Session config
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_KEY_PREFIX = os.environ.get('SESSION_KEY_PREFIX', 'intranet:')
    SESSION_FILE_THRESHOLD = int(os.environ.get('SESSION_FILE_THRESHOLD', '500'))

    # Admin users
    ADMIN_UPNS = [upn.strip() for upn in os.environ.get('ADMIN_UPNS', '').split(',') if upn.strip()]

    # Microsoft Graph API scopes
    SCOPES = ["https://graph.microsoft.com/User.Read"]

    @property
    def AUTHORITY(self):
        """Microsoft authority URL"""
        if self.MS_TENANT_ID:
            return f"https://login.microsoftonline.com/{self.MS_TENANT_ID}"
        return None

    @property
    def REDIRECT_URI(self):
        """Microsoft auth redirect URI"""
        return f"{self.BASE_URL}/auth/callback"

    def __post_init__(self):
        logger.info(f"Config loaded: {self.__class__.__name__}")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

    def __init__(self):
        super().__init__()
        logger.info("Development config loaded")

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        super().__init__()
        # Validate production requirements
        required = ['MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MS_TENANT_ID']
        missing = [var for var in required if not getattr(self, var)]
        if missing:
            raise ValueError(f"Production requires: {', '.join(missing)}")
        logger.info("Production config loaded and validated")

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SESSION_COOKIE_SECURE = False
    DATABASE_PATH = ':memory:'  # In-memory database for tests

    def __init__(self):
        super().__init__()
        logger.info("Testing config loaded")

# Config mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}