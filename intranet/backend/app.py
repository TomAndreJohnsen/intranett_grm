"""
Main Flask application with Microsoft Entra ID authentication.
Provides authentication endpoints and user API for intranet application.
"""
from flask import Flask, request, redirect, url_for, jsonify, session
from flask_session import Session
import os
import redis
import secrets
from config import Config
from auth import auth_manager, login_required


def create_app():
    """
    Create and configure Flask application.

    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Configure session management
    if Config.SESSION_TYPE == 'redis' and Config.REDIS_URL:
        # Use Redis for session storage (recommended for production)
        app.config['SESSION_REDIS'] = redis.from_url(Config.REDIS_URL)
    else:
        # Use filesystem for session storage (development)
        app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
        os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

    # Initialize session extension
    Session(app)

    return app


# Create Flask application
app = create_app()


# Authentication Routes
@app.route('/auth/login')
def auth_login():
    """
    Initiate Microsoft Entra ID login flow.

    Returns:
        Redirect to Microsoft authorization endpoint
    """
    try:
        auth_url, state = auth_manager.get_auth_url()
        return redirect(auth_url)
    except Exception as e:
        return jsonify({'error': 'Failed to initiate login', 'details': str(e)}), 500


@app.route('/auth/callback')
def auth_callback():
    """
    Handle OAuth callback from Microsoft Entra ID.

    Returns:
        Redirect to dashboard or error response
    """
    # Get authorization code and state from callback
    auth_code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    # Handle OAuth errors
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        return jsonify({
            'error': 'OAuth error',
            'error_code': error,
            'description': error_description
        }), 400

    # Handle missing authorization code
    if not auth_code:
        return jsonify({'error': 'Missing authorization code'}), 400

    try:
        # Process the callback and get user info
        user_info = auth_manager.handle_callback(auth_code, state)

        if user_info:
            # Successful authentication - redirect to frontend dashboard
            return redirect(f"{Config.BASE_URL}/#/dashboard")
        else:
            return jsonify({'error': 'Authentication failed'}), 401

    except Exception as e:
        return jsonify({'error': 'Callback processing failed', 'details': str(e)}), 500


@app.route('/auth/logout', methods=['POST'])
@login_required
def auth_logout():
    """
    Log out the current user.

    Returns:
        JSON response with logout URL
    """
    try:
        logout_url = auth_manager.logout()
        return jsonify({
            'success': True,
            'logout_url': logout_url,
            'message': 'Logged out successfully'
        })
    except Exception as e:
        return jsonify({'error': 'Logout failed', 'details': str(e)}), 500


# API Routes
@app.route('/api/me')
@login_required
def api_me():
    """
    Get current user information.

    Returns:
        JSON response with user profile and admin status
    """
    try:
        user_info = auth_manager.get_current_user()
        if user_info:
            # Return essential user information
            return jsonify({
                'id': user_info.get('id'),
                'displayName': user_info.get('displayName'),
                'givenName': user_info.get('givenName'),
                'surname': user_info.get('surname'),
                'userPrincipalName': user_info.get('userPrincipalName'),
                'mail': user_info.get('mail'),
                'jobTitle': user_info.get('jobTitle'),
                'department': user_info.get('department'),
                'is_admin': user_info.get('is_admin', False)
            })
        else:
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        return jsonify({'error': 'Failed to get user info', 'details': str(e)}), 500


@app.route('/api/healthz')
def api_health():
    """
    Health check endpoint.

    Returns:
        JSON response indicating service health
    """
    return jsonify({
        'status': 'ok',
        'service': 'intranet-auth',
        'authenticated': auth_manager.is_authenticated()
    })


# Error Handlers
@app.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized access."""
    return jsonify({'error': 'Unauthorized access'}), 401


@app.errorhandler(403)
def forbidden(error):
    """Handle forbidden access."""
    return jsonify({'error': 'Forbidden access'}), 403


@app.errorhandler(404)
def not_found(error):
    """Handle not found errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    return jsonify({'error': 'Internal server error'}), 500


# CORS headers for frontend integration
@app.after_request
def after_request(response):
    """Add CORS headers to all responses."""
    response.headers.add('Access-Control-Allow-Origin', Config.BASE_URL)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


if __name__ == '__main__':
    # Development server
    try:
        Config.validate_config()

        # Get port from environment variable, default to 5000
        port = int(os.environ.get('PORT', 5000))

        print("Starting intranet authentication service...")
        print(f"Base URL: {Config.BASE_URL}")
        print(f"Running on port: {port}")
        print(f"Session type: {Config.SESSION_TYPE}")
        print(f"Admin users: {len(Config.ADMIN_UPNS)} configured")

        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
    except Exception as e:
        print(f"Failed to start application: {e}")