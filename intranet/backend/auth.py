"""
Microsoft Entra ID authentication module using MSAL.
Handles OAuth2 flow, token management, and user session management.
"""
import uuid
import msal
import requests
import logging
import os
from flask import session, request, url_for, redirect, jsonify, flash
from functools import wraps
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthManager:
    """Manages Microsoft Entra ID authentication using MSAL."""

    def __init__(self):
        """Initialize the authentication manager."""
        self.msal_app = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of MSAL client."""
        if not self._initialized:
            try:
                # Validate configuration
                Config.validate_config()

                # Initialize MSAL confidential client
                self.msal_app = msal.ConfidentialClientApplication(
                    Config.CLIENT_ID,
                    authority=Config.AUTHORITY,
                    client_credential=Config.CLIENT_SECRET
                )
                self._initialized = True
            except Exception as e:
                raise ValueError(f"Authentication configuration error: {str(e)}")

    def get_auth_url(self):
        """
        Generate the Microsoft login URL.

        Returns:
            tuple: (auth_url, state) - Authorization URL and state parameter
        """
        # Ensure MSAL client is initialized
        self._ensure_initialized()

        # Generate a unique state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['auth_state'] = state

        # Get dynamic redirect URI based on current request
        redirect_uri = Config.get_redirect_uri()
        logger.info(f"Using redirect_uri: {redirect_uri}")

        # Build authorization URL
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=list(Config.SCOPES),
            state=state,
            redirect_uri=redirect_uri
        )

        logger.info(f"Generated auth URL with state: {state}")
        return auth_url, state

    def handle_callback(self, auth_code, state):
        """
        Handle the OAuth callback from Microsoft.

        Args:
            auth_code (str): Authorization code from Microsoft
            state (str): State parameter for CSRF protection

        Returns:
            dict: User information if successful, None if failed
        """
        logger.info(f"Starting callback handling with state: {state}")
        logger.info(f"Session auth_state: {session.get('auth_state')}")

        # Ensure MSAL client is initialized
        self._ensure_initialized()

        # Verify state parameter to prevent CSRF attacks
        if state != session.get('auth_state'):
            logger.error(f"State mismatch - received: {state}, expected: {session.get('auth_state')}")
            return None

        # Get dynamic redirect URI (same as used in auth URL)
        redirect_uri = Config.get_redirect_uri()
        logger.info(f"Using redirect_uri for token exchange: {redirect_uri}")

        # Exchange authorization code for access token
        result = self.msal_app.acquire_token_by_authorization_code(
            auth_code,
            scopes=list(Config.SCOPES),
            redirect_uri=redirect_uri
        )

        logger.info(f"Token exchange result keys: {list(result.keys())}")

        if 'error' in result:
            error_msg = result.get('error_description', result.get('error', 'Unknown error'))
            logger.error(f"Token exchange failed: {error_msg}")
            return None

        logger.info("Token exchange successful")

        # Store tokens in session
        session['access_token'] = result.get('access_token')
        session['id_token'] = result.get('id_token')
        session['user_id'] = result.get('id_token_claims', {}).get('oid')

        logger.info(f"Stored tokens in session. User ID: {session.get('user_id')}")

        # Fetch user profile from Microsoft Graph
        user_info = self.get_user_profile(result.get('access_token'))
        if user_info:
            # Store user information in session
            session['user'] = user_info
            session['is_admin'] = user_info.get('userPrincipalName', '').lower() in [upn.lower() for upn in Config.ADMIN_UPNS]

            logger.info(f"User profile stored in session: {user_info.get('userPrincipalName')}")
            logger.info(f"User is admin: {session.get('is_admin')}")

            # Ensure session is saved
            session.permanent = True
        else:
            logger.error("Failed to fetch user profile from Microsoft Graph")

        # Clear the auth state
        session.pop('auth_state', None)

        logger.info("Session after callback processing:")
        logger.info(f"  - user present: {'user' in session}")
        logger.info(f"  - access_token present: {'access_token' in session}")
        logger.info(f"  - session keys: {list(session.keys())}")

        return user_info

    def get_user_profile(self, access_token):
        """
        Fetch user profile from Microsoft Graph API.

        Args:
            access_token (str): Access token for Microsoft Graph

        Returns:
            dict: User profile information
        """
        if not access_token:
            logger.error("No access token provided for user profile fetch")
            return None

        # Microsoft Graph API endpoint for user profile
        graph_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        try:
            logger.info("Fetching user profile from Microsoft Graph")
            response = requests.get(graph_url, headers=headers, timeout=10)
            response.raise_for_status()
            user_data = response.json()
            logger.info(f"Successfully fetched profile for: {user_data.get('userPrincipalName')}")
            return user_data
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user profile: {str(e)}")
            return None

    def refresh_token(self):
        """
        Refresh the access token if needed.

        Returns:
            bool: True if token was refreshed successfully
        """
        if 'user_id' not in session:
            return False

        # Ensure MSAL client is initialized
        try:
            self._ensure_initialized()
        except ValueError:
            return False

        # Get account from cache
        accounts = self.msal_app.get_accounts(username=session.get('user', {}).get('userPrincipalName'))
        if not accounts:
            return False

        # Try to get token silently
        result = self.msal_app.acquire_token_silent(
            scopes=list(Config.SCOPES),
            account=accounts[0]
        )

        if 'access_token' in result:
            session['access_token'] = result['access_token']
            return True

        return False

    def logout(self):
        """Clear user session and return Microsoft logout URL."""
        # Clear all session data
        session.clear()

        # Return Microsoft logout URL
        logout_url = f"{Config.AUTHORITY}/oauth2/v2.0/logout?post_logout_redirect_uri={Config.BASE_URL}"
        return logout_url

    def is_authenticated(self):
        """
        Check if the current user is authenticated.

        Returns:
            bool: True if user is authenticated
        """
        return 'user' in session and 'access_token' in session

    def get_current_user(self):
        """
        Get current user information from session.

        Returns:
            dict: Current user information or None
        """
        if self.is_authenticated():
            user_data = session.get('user', {})
            user_data['is_admin'] = session.get('is_admin', False)
            return user_data
        return None


# Global auth manager instance
auth_manager = AuthManager()


def login_required(f):
    """
    Decorator to require authentication for a route.

    Args:
        f: Function to wrap

    Returns:
        Wrapped function that checks authentication
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            # For API routes, return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401

            # For web routes, redirect to login
            return redirect(url_for('auth_login'))

        # Try to refresh token if needed
        auth_manager.refresh_token()

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin privileges for a route.

    Args:
        f: Function to wrap

    Returns:
        Wrapped function that checks admin privileges
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth_login'))

        if not session.get('is_admin', False):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin privileges required'}), 403
            return jsonify({'error': 'Admin privileges required'}), 403

        return f(*args, **kwargs)
    return decorated_function