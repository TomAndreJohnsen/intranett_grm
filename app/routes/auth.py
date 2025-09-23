import logging
import os
import uuid
import msal
import requests
from typing import Optional, Dict, Tuple
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from functools import wraps

bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

class AuthManager:
    """Manages Microsoft Entra ID authentication with comprehensive logging."""

    def __init__(self):
        self.msal_app = None
        self._check_config()

    def _check_config(self):
        """Check if all required config values are present."""
        required_vars = ['MS_CLIENT_ID', 'MS_CLIENT_SECRET', 'MS_TENANT_ID', 'APP_BASE_URL']
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.warning(f"Missing environment variables: {missing_vars}")
            logger.info("Will use demo mode authentication")
            return False

        logger.info("Microsoft Entra ID configuration found")
        return True

    def _ensure_initialized(self):
        """Ensure MSAL client is initialized."""
        if self.msal_app is None and self._check_config():
            authority = f"https://login.microsoftonline.com/{os.getenv('MS_TENANT_ID')}"

            self.msal_app = msal.ConfidentialClientApplication(
                client_id=os.getenv('MS_CLIENT_ID'),
                client_credential=os.getenv('MS_CLIENT_SECRET'),
                authority=authority
            )
            logger.info(f"MSAL client initialized with authority: {authority}")

    def get_auth_url(self) -> Tuple[str, str]:
        """Generate Microsoft Entra ID authentication URL."""
        self._ensure_initialized()

        if not self.msal_app:
            logger.error("MSAL client not available - missing configuration")
            raise Exception("Microsoft authentication not configured")

        # Generate state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['auth_state'] = state

        # Build redirect URI from environment
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        redirect_uri = f"{base_url}/auth/callback"

        logger.info(f"Generated auth URL with redirect_uri: {redirect_uri}")
        logger.info(f"Auth state generated: {state}")

        scopes = ["openid", "profile", "email", "User.Read"]

        auth_url = self.msal_app.get_authorization_request_url(
            scopes=scopes,
            state=state,
            redirect_uri=redirect_uri
        )

        logger.info(f"Authentication URL generated successfully")
        return auth_url, state

    def handle_callback(self, auth_code: str, state: str) -> Optional[Dict]:
        """Handle OAuth callback from Microsoft with comprehensive logging."""
        logger.info("=== HANDLING AUTH CALLBACK ===")
        logger.info(f"Received auth_code: {'YES' if auth_code else 'NO'}")
        logger.info(f"Received state: {state}")
        logger.info(f"Session auth_state: {session.get('auth_state')}")

        self._ensure_initialized()

        if not self.msal_app:
            logger.error("MSAL client not available during callback")
            return None

        # Verify state parameter to prevent CSRF attacks
        expected_state = session.get('auth_state')
        if state != expected_state:
            logger.error(f"State mismatch! Expected: {expected_state}, Got: {state}")
            return None

        logger.info("State verification passed")

        # Build redirect URI (must match exactly what we sent to Azure)
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        redirect_uri = f"{base_url}/auth/callback"

        logger.info(f"Using redirect_uri for token exchange: {redirect_uri}")

        # Exchange authorization code for access token
        try:
            logger.info("Attempting token exchange...")

            result = self.msal_app.acquire_token_by_authorization_code(
                auth_code,
                scopes=["openid", "profile", "email", "User.Read"],
                redirect_uri=redirect_uri
            )

            logger.info(f"Token exchange result keys: {list(result.keys())}")

            if 'error' in result:
                logger.error(f"Token exchange failed: {result.get('error')}")
                logger.error(f"Error description: {result.get('error_description')}")
                return None

            logger.info("Token exchange successful!")

            # Store tokens in session
            session['access_token'] = result.get('access_token')
            session['id_token'] = result.get('id_token')
            session['user_id'] = result.get('id_token_claims', {}).get('oid')

            logger.info("Tokens stored in session")

            # Fetch user profile from Microsoft Graph
            user_info = self.get_user_profile(result.get('access_token'))

            if user_info:
                logger.info(f"User profile fetched: {user_info.get('displayName')} ({user_info.get('userPrincipalName')})")

                # Store user information in session
                session['user'] = user_info
                session['user_name'] = user_info.get('displayName', user_info.get('userPrincipalName', 'Unknown User'))

                # Check admin status
                admin_upns = [upn.strip().lower() for upn in os.getenv('ADMIN_UPNS', '').split(',') if upn.strip()]
                user_upn = user_info.get('userPrincipalName', '').lower()
                is_admin = user_upn in admin_upns
                session['is_admin'] = is_admin

                logger.info(f"User admin status: {is_admin}")
                logger.info("=== USER SUCCESSFULLY STORED IN SESSION ===")
            else:
                logger.error("Failed to fetch user profile from Graph API")

            # Clear the auth state
            session.pop('auth_state', None)

            return user_info

        except Exception as e:
            logger.error(f"Exception during token exchange: {str(e)}")
            logger.exception("Full exception details:")
            return None

    def get_user_profile(self, access_token: str) -> Optional[Dict]:
        """Fetch user profile from Microsoft Graph API."""
        if not access_token:
            logger.error("No access token provided for Graph API call")
            return None

        graph_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        try:
            logger.info("Calling Microsoft Graph API for user profile")
            response = requests.get(graph_url, headers=headers, timeout=10)
            response.raise_for_status()

            user_data = response.json()
            logger.info("Microsoft Graph API call successful")
            return user_data

        except requests.RequestException as e:
            logger.error(f"Microsoft Graph API call failed: {str(e)}")
            return None

    def logout(self) -> str:
        """Clear user session and return Microsoft logout URL."""
        logger.info("Logging out user")

        # Clear all session data
        session.clear()

        # Return Microsoft logout URL
        base_url = os.getenv('APP_BASE_URL', 'http://localhost:5000')
        tenant_id = os.getenv('MS_TENANT_ID')

        if tenant_id:
            logout_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={base_url}"
        else:
            logout_url = base_url

        logger.info(f"Logout URL: {logout_url}")
        return logout_url

    def is_authenticated(self) -> bool:
        """Check if the current user is authenticated."""
        has_user = 'user' in session
        has_token = 'access_token' in session

        logger.debug(f"Auth check - has_user: {has_user}, has_token: {has_token}")
        return has_user and has_token

    def get_current_user(self) -> Optional[Dict]:
        """Get current user information from session."""
        if self.is_authenticated():
            user_data = session.get('user', {})
            user_data['is_admin'] = session.get('is_admin', False)
            return user_data
        return None

# Create global auth manager instance
auth_manager = AuthManager()

# Authentication decorator
def auth_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions for templates
def get_current_user():
    """Get current user for template use."""
    return auth_manager.get_current_user()

def get_user_display_name():
    """Get user display name for template use."""
    user = get_current_user()
    if user:
        return user.get('displayName', user.get('userPrincipalName', 'Unknown User'))
    return 'Demo User'

def get_user_email():
    """Get user email for template use."""
    user = get_current_user()
    if user:
        return user.get('userPrincipalName', user.get('mail', ''))
    return 'demo@example.com'

# Auth routes
@bp.route('/login')
def login():
    """Initiate Microsoft Entra ID login flow or demo login."""
    logger.info("User accessing login page")

    # Check if already authenticated
    if auth_manager.is_authenticated():
        logger.info("User already authenticated, redirecting to dashboard")
        return redirect(url_for('dashboard.index'))

    # Check if Microsoft auth is configured
    if not auth_manager._check_config():
        logger.info("Microsoft auth not configured - using demo login")

        # Demo mode: automatically log in a demo user
        session['user'] = {
            'displayName': 'Demo User',
            'userPrincipalName': 'demo@example.com',
            'id': 'demo-user-id'
        }
        session['user_name'] = 'Demo User'
        session['access_token'] = 'demo-token'
        session['is_admin'] = True

        logger.info("Demo user logged in successfully")
        return redirect(url_for('dashboard.index'))

    try:
        logger.info("Initiating Microsoft Entra ID login flow")
        auth_url, state = auth_manager.get_auth_url()
        logger.info(f"Redirecting to Microsoft auth URL")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Failed to initiate login: {str(e)}")
        flash(f'Login initiation failed: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@bp.route('/callback')
def callback():
    """Handle OAuth callback from Microsoft Entra ID."""
    logger.info("=== AUTH CALLBACK RECEIVED ===")

    # Log all request arguments for debugging
    logger.info(f"Request args: {dict(request.args)}")

    # Get authorization code and state from callback
    auth_code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    logger.info(f"Auth code present: {'YES' if auth_code else 'NO'}")
    logger.info(f"State: {state}")
    logger.info(f"Error: {error}")
    logger.info(f"Error description: {error_description}")

    # Handle OAuth errors
    if error:
        logger.error(f"OAuth error: {error} - {error_description}")
        flash(f'Login error: {error_description or error}', 'error')
        return redirect(url_for('dashboard.index'))

    # Handle missing authorization code
    if not auth_code:
        logger.error("Missing authorization code in callback")
        flash('Missing authorization code', 'error')
        return redirect(url_for('dashboard.index'))

    try:
        # Process the callback and get user info
        logger.info("Processing callback...")
        user_info = auth_manager.handle_callback(auth_code, state)

        if user_info:
            logger.info("Authentication successful!")
            display_name = user_info.get('displayName', 'User')
            flash(f'Velkommen, {display_name}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            logger.error("Authentication failed - no user info returned")
            flash('Authentication failed', 'error')
            return redirect(url_for('dashboard.index'))

    except Exception as e:
        logger.error(f"Callback processing failed: {str(e)}")
        logger.exception("Full exception details:")
        flash(f'Callback processing failed: {str(e)}', 'error')
        return redirect(url_for('dashboard.index'))

@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Log out the current user."""
    logger.info("User logging out")

    try:
        logout_url = auth_manager.logout()

        # For AJAX requests, return JSON
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True,
                'logout_url': logout_url,
                'message': 'Logged out successfully'
            })

        # For regular requests, redirect to logout URL
        flash('Du er nå logget ut', 'success')
        return redirect(logout_url)

    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        flash('Logout failed', 'error')
        return redirect(url_for('dashboard.index'))

@bp.route('/status')
def status():
    """Get authentication status for debugging."""
    return jsonify({
        'authenticated': auth_manager.is_authenticated(),
        'user': auth_manager.get_current_user(),
        'session_keys': list(session.keys()),
        'config_available': auth_manager._check_config()
    })