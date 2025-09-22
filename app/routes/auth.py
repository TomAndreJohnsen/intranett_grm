import logging
import uuid
from typing import Optional, Dict, Any, Tuple
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
import msal
import requests
from ..utils.helpers import auth_required

bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

class AuthManager:
    """Manages Microsoft Entra ID authentication using MSAL"""

    def __init__(self):
        """Initialize the authentication manager"""
        self.msal_app = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of MSAL client"""
        if not self._initialized:
            try:
                # Check if we have MS configuration
                if not all([
                    current_app.config.get('MS_CLIENT_ID'),
                    current_app.config.get('MS_CLIENT_SECRET'),
                    current_app.config.get('MS_TENANT_ID')
                ]):
                    logger.warning("Microsoft authentication not configured - using demo mode")
                    return False

                # Initialize MSAL confidential client
                self.msal_app = msal.ConfidentialClientApplication(
                    current_app.config['MS_CLIENT_ID'],
                    authority=current_app.config['AUTHORITY'],
                    client_credential=current_app.config['MS_CLIENT_SECRET']
                )
                self._initialized = True
                logger.info("Microsoft authentication initialized")
                return True
            except Exception as e:
                logger.error(f"Authentication configuration error: {str(e)}")
                return False
        return True

    def get_auth_url(self) -> Tuple[Optional[str], Optional[str]]:
        """Generate the Microsoft login URL"""
        if not self._ensure_initialized():
            return None, None

        # Generate a unique state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['auth_state'] = state

        # Build authorization URL
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=list(current_app.config['SCOPES']),
            state=state,
            redirect_uri=current_app.config['REDIRECT_URI']
        )

        logger.info("Generated Microsoft auth URL")
        return auth_url, state

    def handle_callback(self, auth_code: str, state: str) -> Optional[Dict[str, Any]]:
        """Handle the OAuth callback from Microsoft"""
        if not self._ensure_initialized():
            return None

        # Verify state parameter to prevent CSRF attacks
        if state != session.get('auth_state'):
            logger.warning("Auth state mismatch - possible CSRF attack")
            return None

        # Exchange authorization code for access token
        result = self.msal_app.acquire_token_by_authorization_code(
            auth_code,
            scopes=list(current_app.config['SCOPES']),
            redirect_uri=current_app.config['REDIRECT_URI']
        )

        if 'error' in result:
            logger.error(f"Token acquisition failed: {result.get('error_description')}")
            return None

        # Store tokens in session
        session['access_token'] = result.get('access_token')
        session['id_token'] = result.get('id_token')
        session['user_id'] = result.get('id_token_claims', {}).get('oid')

        # Fetch user profile from Microsoft Graph
        user_info = self.get_user_profile(result.get('access_token'))
        if user_info:
            # Store user information in session
            session['user'] = user_info
            upn = user_info.get('userPrincipalName', '').lower()
            admin_upns = [upn.lower() for upn in current_app.config['ADMIN_UPNS']]
            session['is_admin'] = upn in admin_upns

            logger.info(f"User logged in: {user_info.get('displayName')} ({upn})")

        # Clear the auth state
        session.pop('auth_state', None)

        return user_info

    def get_user_profile(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile from Microsoft Graph API"""
        if not access_token:
            return None

        # Microsoft Graph API endpoint for user profile
        graph_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(graph_url, headers=headers, timeout=10)
            response.raise_for_status()
            user_data = response.json()
            logger.debug(f"Retrieved user profile: {user_data.get('displayName')}")
            return user_data
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user profile: {str(e)}")
            return None

    def logout(self) -> str:
        """Clear user session and return Microsoft logout URL"""
        user_name = session.get('user', {}).get('displayName', 'Unknown')
        session.clear()
        logger.info(f"User logged out: {user_name}")

        # Return Microsoft logout URL if configured
        if current_app.config.get('MS_TENANT_ID'):
            logout_url = f"{current_app.config['AUTHORITY']}/oauth2/v2.0/logout?post_logout_redirect_uri={current_app.config['BASE_URL']}"
            return logout_url
        return current_app.config['BASE_URL']

# Global auth manager instance
auth_manager = AuthManager()

@bp.route('/login')
def login():
    """Login side"""
    logger.info("User accessing login page")

    # Check if Microsoft auth is configured
    if not all([
        current_app.config.get('MS_CLIENT_ID'),
        current_app.config.get('MS_CLIENT_SECRET'),
        current_app.config.get('MS_TENANT_ID')
    ]):
        # Demo mode - auto login as demo user
        logger.info("Microsoft auth not configured - using demo login")
        session['user'] = {
            'displayName': 'Demo User',
            'userPrincipalName': 'demo@grm.no',
            'id': 'demo-user-123'
        }
        session['is_admin'] = True
        flash('Logget inn som demo bruker (Microsoft auth ikke konfigurert)', 'info')
        return redirect(url_for('dashboard.index'))

    auth_url, state = auth_manager.get_auth_url()
    if not auth_url:
        flash('Microsoft authentication er ikke tilgjengelig', 'error')
        return render_template('auth/login.html', auth_url=None)

    return render_template('auth/login.html', auth_url=auth_url)

@bp.route('/callback')
def callback():
    """Microsoft auth callback"""
    logger.info("Auth callback received")

    if 'error' in request.args:
        error_msg = request.args.get('error_description', 'Unknown error')
        logger.error(f"Auth error: {error_msg}")
        flash(f"Login error: {error_msg}", 'error')
        return redirect(url_for('auth.login'))

    if 'code' not in request.args:
        flash("Missing authorization code", 'error')
        return redirect(url_for('auth.login'))

    try:
        result = auth_manager.handle_callback(
            request.args['code'],
            request.args.get('state')
        )
        if result:
            flash('Innlogging vellykket!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash("Authentication failed", 'error')
            return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        flash(f"Authentication error: {str(e)}", 'error')
        return redirect(url_for('auth.login'))

@bp.route('/logout')
@auth_required
def logout():
    """Logg ut bruker"""
    logout_url = auth_manager.logout()
    flash("Du har blitt logget ut", 'success')

    # Redirect to Microsoft logout if configured, otherwise local
    if logout_url != current_app.config['BASE_URL']:
        return redirect(logout_url)
    return redirect(url_for('auth.login'))

# API endpoints
@bp.route('/api/me')
@auth_required
def api_me():
    """Get current user info"""
    user = session.get('user', {})
    return jsonify({
        'name': user.get('displayName', 'Unknown'),
        'email': user.get('userPrincipalName', 'unknown@example.com'),
        'is_admin': session.get('is_admin', False)
    })

@bp.route('/api/status')
def api_status():
    """Auth status endpoint"""
    ms_configured = all([
        current_app.config.get('MS_CLIENT_ID'),
        current_app.config.get('MS_CLIENT_SECRET'),
        current_app.config.get('MS_TENANT_ID')
    ])

    return jsonify({
        'authenticated': 'user' in session,
        'microsoft_configured': ms_configured,
        'demo_mode': not ms_configured
    })