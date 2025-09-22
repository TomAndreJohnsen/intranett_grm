import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional
from flask import session, redirect, url_for, request, jsonify

logger = logging.getLogger(__name__)

def auth_required(f: Callable) -> Callable:
    """Krever at brukeren er logget inn"""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'user' not in session:
            logger.warning(f"Unauthorized access attempt to {request.endpoint} from {request.remote_addr}")
            if request.endpoint and request.endpoint.startswith('api.'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """Krever admin-rettigheter"""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'user' not in session:
            logger.warning(f"Unauthorized access attempt to {request.endpoint}")
            return redirect(url_for('auth.login'))

        user_upn = session['user'].get('userPrincipalName', '')
        from flask import current_app
        if user_upn not in current_app.config['ADMIN_UPNS']:
            logger.warning(f"Non-admin user {user_upn} attempted admin action: {request.endpoint}")
            return jsonify({'error': 'Admin access required'}), 403

        return f(*args, **kwargs)
    return decorated_function

def get_current_user() -> Optional[Dict[str, Any]]:
    """Hent nåværende bruker fra session"""
    user = session.get('user')
    if user:
        logger.debug(f"Current user: {user.get('displayName', 'Unknown')}")
    return user

def is_authenticated() -> bool:
    """Sjekk om bruker er logget inn"""
    return 'user' in session

def is_admin() -> bool:
    """Sjekk om nåværende bruker har admin-rettigheter"""
    if not is_authenticated():
        return False

    user_upn = session['user'].get('userPrincipalName', '')
    from flask import current_app
    return user_upn in current_app.config['ADMIN_UPNS']

def get_user_display_name() -> str:
    """Hent display name for nåværende bruker"""
    if not is_authenticated():
        return 'Anonymous'

    return session['user'].get('displayName', 'Unknown User')

def get_user_email() -> str:
    """Hent email for nåværende bruker"""
    if not is_authenticated():
        return 'anonymous@example.com'

    return session['user'].get('userPrincipalName', 'unknown@example.com')