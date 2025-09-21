"""
Unified GRM Intranet application with integrated Microsoft Entra ID authentication.
Combines the main intranet functionality with authentication backend in a single Flask app.
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_session import Session
from werkzeug.utils import secure_filename
import sqlite3
import os
import uuid
import msal
import requests
from datetime import datetime
import json
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration class
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

    # Admin users (comma-separated UPNs)
    ADMIN_UPNS = [upn.strip() for upn in os.environ.get('ADMIN_UPNS', '').split(',') if upn.strip()]

    # Session configuration
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


# Authentication Manager
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
        """Generate the Microsoft login URL."""
        # Ensure MSAL client is initialized
        self._ensure_initialized()

        # Generate a unique state parameter for CSRF protection
        state = str(uuid.uuid4())
        session['auth_state'] = state

        # Build authorization URL
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=list(Config.SCOPES),
            state=state,
            redirect_uri=Config.REDIRECT_URI
        )

        return auth_url, state

    def handle_callback(self, auth_code, state):
        """Handle the OAuth callback from Microsoft."""
        # Ensure MSAL client is initialized
        self._ensure_initialized()

        # Verify state parameter to prevent CSRF attacks
        if state != session.get('auth_state'):
            return None

        # Exchange authorization code for access token
        result = self.msal_app.acquire_token_by_authorization_code(
            auth_code,
            scopes=list(Config.SCOPES),
            redirect_uri=Config.REDIRECT_URI
        )

        if 'error' in result:
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
            session['is_admin'] = user_info.get('userPrincipalName', '').lower() in [upn.lower() for upn in Config.ADMIN_UPNS]

        # Clear the auth state
        session.pop('auth_state', None)

        return user_info

    def get_user_profile(self, access_token):
        """Fetch user profile from Microsoft Graph API."""
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
            return response.json()
        except requests.RequestException:
            return None

    def logout(self):
        """Clear user session and return Microsoft logout URL."""
        # Clear all session data
        session.clear()

        # Return Microsoft logout URL
        logout_url = f"{Config.AUTHORITY}/oauth2/v2.0/logout?post_logout_redirect_uri={Config.BASE_URL}"
        return logout_url

    def is_authenticated(self):
        """Check if the current user is authenticated."""
        return 'user' in session and 'access_token' in session

    def get_current_user(self):
        """Get current user information from session."""
        if self.is_authenticated():
            user_data = session.get('user', {})
            user_data['is_admin'] = session.get('is_admin', False)
            return user_data
        return None


# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Configure session management
if Config.SESSION_TYPE == 'redis' and os.environ.get('REDIS_URL'):
    import redis
    app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL'))
else:
    # Use filesystem for session storage (development)
    app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize session extension
Session(app)

# Create upload directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'salg'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'verksted'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'hms'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'it'), exist_ok=True)

# Initialize auth manager
auth_manager = AuthManager()


# Authentication decorators
def auth_required(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            # For API routes, return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            # For web routes, redirect to login
            return redirect(url_for('auth_login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth_login'))

        if not session.get('is_admin', False):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin privileges required'}), 403
            flash('Admin privileges required')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated_function


# Helper function to get current user
def get_current_user():
    """Get current user from session."""
    return auth_manager.get_current_user()


# Database initialization
def init_db():
    """Initialize database with required tables."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Posts table (newsfeed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            user_name TEXT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_email TEXT,
            user_name TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    ''')

    # Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            folder TEXT NOT NULL,
            uploaded_by_email TEXT,
            uploaded_by_name TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Calendar events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_date DATE NOT NULL,
            end_date DATE,
            start_time TIME,
            end_time TIME,
            location TEXT,
            responsible_user_email TEXT,
            responsible_user_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tasks/Issues table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            department TEXT,
            assigned_to_email TEXT,
            assigned_to_name TEXT,
            created_by_email TEXT,
            created_by_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Newsletter table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            sent_date TIMESTAMP,
            created_by_email TEXT,
            created_by_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Suppliers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT,
            password TEXT,
            website TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default suppliers if not exists
    cursor.execute('SELECT COUNT(*) FROM suppliers')
    if cursor.fetchone()[0] == 0:
        suppliers_data = [
            ('Bosch', 'grm_bosch', 'B0sch2023!', 'https://www.bosch.com'),
            ('Makita', 'grm_makita', 'Mak1ta#2023', 'https://www.makita.com'),
            ('Dewalt', 'grm_dewalt', 'DeW@lt456', 'https://www.dewalt.com'),
            ('Festool', 'grm_festool', 'F3st00l789', 'https://www.festool.com')
        ]
        cursor.executemany('''
            INSERT INTO suppliers (name, username, password, website)
            VALUES (?, ?, ?, ?)
        ''', suppliers_data)

    conn.commit()
    conn.close()


# Authentication Routes
@app.route('/auth/login')
def auth_login():
    """Initiate Microsoft Entra ID login flow."""
    try:
        auth_url, state = auth_manager.get_auth_url()
        return redirect(auth_url)
    except Exception as e:
        return jsonify({'error': 'Failed to initiate login', 'details': str(e)}), 500


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback from Microsoft Entra ID."""
    # Get authorization code and state from callback
    auth_code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    # Handle OAuth errors
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        flash(f'Login error: {error_description}')
        return redirect(url_for('home'))

    # Handle missing authorization code
    if not auth_code:
        flash('Missing authorization code')
        return redirect(url_for('home'))

    try:
        # Process the callback and get user info
        user_info = auth_manager.handle_callback(auth_code, state)

        if user_info:
            # Successful authentication - redirect to dashboard
            flash(f'Welcome, {user_info.get("displayName", "User")}!')
            return redirect(url_for('dashboard'))
        else:
            flash('Authentication failed')
            return redirect(url_for('home'))

    except Exception as e:
        flash(f'Callback processing failed: {str(e)}')
        return redirect(url_for('home'))


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    """Log out the current user."""
    try:
        logout_url = auth_manager.logout()
        # For AJAX requests, return JSON
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True,
                'logout_url': logout_url,
                'message': 'Logged out successfully'
            })
        # For form submissions, redirect
        return redirect(logout_url)
    except Exception as e:
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'error': 'Logout failed', 'details': str(e)}), 500
        flash('Logout failed')
        return redirect(url_for('home'))


@app.route('/api/me')
def api_me():
    """Get current user information."""
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
            return jsonify({'error': 'User not found'}), 401

    except Exception as e:
        return jsonify({'error': 'Failed to get user info', 'details': str(e)}), 500


@app.route('/api/healthz')
def api_health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'intranet-unified',
        'authenticated': auth_manager.is_authenticated()
    })


# Main Application Routes
@app.route('/')
def home():
    """Home page."""
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard'))
    return render_template('base.html', user=user)


@app.route('/dashboard')
@auth_required
def dashboard():
    """Main dashboard page."""
    user = get_current_user()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get recent newsletters (only sent ones for regular users, all for admin)
    if user.get('is_admin', False):
        cursor.execute('''
            SELECT n.id, n.title, n.content, n.sent_date, n.created_at, n.created_by_name
            FROM newsletters n
            ORDER BY n.created_at DESC
            LIMIT 10
        ''')
    else:
        cursor.execute('''
            SELECT n.id, n.title, n.content, n.sent_date, n.created_at, n.created_by_name
            FROM newsletters n
            WHERE n.sent_date IS NOT NULL
            ORDER BY n.sent_date DESC
            LIMIT 10
        ''')
    newsletters = cursor.fetchall()

    # Get recent tasks
    cursor.execute('''
        SELECT t.id, t.title, t.status, t.priority, t.assigned_to_name
        FROM tasks t
        WHERE t.status != 'completed'
        ORDER BY t.created_at DESC
        LIMIT 5
    ''')
    tasks = cursor.fetchall()

    # Get upcoming calendar events
    cursor.execute('''
        SELECT c.id, c.title, c.start_date, c.start_time, c.location, c.responsible_user_name
        FROM calendar_events c
        WHERE c.start_date >= date('now')
        ORDER BY c.start_date, c.start_time
        LIMIT 5
    ''')
    events = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html', user=user, newsletters=newsletters, tasks=tasks, events=events)


@app.route('/documents')
@app.route('/documents/<folder>')
@auth_required
def documents(folder=None):
    """Documents page."""
    user = get_current_user()
    allowed_folders = ['salg', 'verksted', 'hms', 'it']

    if folder and folder not in allowed_folders:
        flash('Ugyldig mappe')
        return redirect(url_for('documents'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if folder:
        cursor.execute('''
            SELECT d.id, d.original_filename, d.filename, d.upload_date, d.uploaded_by_name
            FROM documents d
            WHERE d.folder = ?
            ORDER BY d.upload_date DESC
        ''', (folder,))
        documents_list = cursor.fetchall()
    else:
        documents_list = []

    conn.close()

    return render_template('documents.html', user=user,
                         current_folder=folder,
                         documents=documents_list,
                         folders=allowed_folders)


@app.route('/upload_document', methods=['POST'])
@auth_required
def upload_document():
    """Handle document upload."""
    user = get_current_user()

    if 'file' not in request.files:
        flash('Ingen fil valgt')
        return redirect(request.referrer)

    file = request.files['file']
    folder = request.form.get('folder')

    if file.filename == '' or not folder:
        flash('Vennligst velg fil og mappe')
        return redirect(request.referrer)

    if folder not in ['salg', 'verksted', 'hms', 'it']:
        flash('Ugyldig mappe')
        return redirect(request.referrer)

    if file:
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, unique_filename)
        file.save(file_path)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (filename, original_filename, folder, uploaded_by_email, uploaded_by_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (unique_filename, filename, folder, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()

        flash(f'Fil "{filename}" lastet opp til {folder.title()}')

    return redirect(url_for('documents', folder=folder))


@app.route('/download/<int:doc_id>')
@auth_required
def download_document(doc_id):
    """Download document."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT filename, original_filename, folder FROM documents WHERE id = ?', (doc_id,))
    doc = cursor.fetchone()
    conn.close()

    if doc:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc[2])
        return send_from_directory(file_path, doc[0], as_attachment=True, download_name=doc[1])
    else:
        flash('Fil ikke funnet')
        return redirect(url_for('documents'))


@app.route('/calendar')
@auth_required
def calendar():
    """Calendar page."""
    user = get_current_user()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.id, c.title, c.description, c.start_date, c.end_date,
               c.start_time, c.end_time, c.location, c.responsible_user_name
        FROM calendar_events c
        ORDER BY c.start_date, c.start_time
    ''')
    events = cursor.fetchall()

    conn.close()

    return render_template('calendar.html', user=user, events=events)


@app.route('/create_event', methods=['POST'])
@auth_required
def create_event():
    """Create calendar event."""
    user = get_current_user()

    title = request.form.get('title')
    description = request.form.get('description')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    location = request.form.get('location')

    if title and start_date:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO calendar_events
            (title, description, start_date, end_date, start_time, end_time, location, responsible_user_email, responsible_user_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, start_date, end_date, start_time, end_time, location, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()

        flash('Hendelse opprettet!')
    else:
        flash('Tittel og startdato er påkrevd')

    return redirect(url_for('calendar'))


@app.route('/tasks')
@auth_required
def tasks():
    """Tasks page."""
    user = get_current_user()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT t.id, t.title, t.description, t.status, t.priority, t.department,
               t.created_at, t.created_by_name, t.assigned_to_name
        FROM tasks t
        ORDER BY
            CASE t.status
                WHEN 'todo' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'completed' THEN 3
            END,
            CASE t.priority
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END,
            t.created_at DESC
    ''')
    tasks_list = cursor.fetchall()

    conn.close()

    return render_template('tasks.html', user=user, tasks=tasks_list)


@app.route('/create_task', methods=['POST'])
@auth_required
def create_task():
    """Create task."""
    user = get_current_user()

    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority', 'medium')
    department = request.form.get('department')
    assigned_to = request.form.get('assigned_to')

    if title:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, department, assigned_to_name, created_by_email, created_by_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, priority, department, assigned_to or None, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()

        flash('Oppgave opprettet!')
    else:
        flash('Tittel er påkrevd')

    return redirect(url_for('tasks'))


@app.route('/update_task_status', methods=['POST'])
@auth_required
def update_task_status():
    """Update task status."""
    task_id = request.form.get('task_id')
    new_status = request.form.get('status')

    if task_id and new_status in ['todo', 'in_progress', 'completed']:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      (new_status, task_id))
        conn.commit()
        conn.close()

        flash('Oppgavestatus oppdatert!')
    else:
        flash('Ugyldig oppgave eller status')

    return redirect(url_for('tasks'))


@app.route('/newsletter')
@auth_required
def newsletter():
    """Newsletter page."""
    user = get_current_user()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT n.id, n.title, n.content, n.sent_date, n.created_at, n.created_by_name
        FROM newsletters n
        ORDER BY n.created_at DESC
    ''')
    newsletters = cursor.fetchall()

    conn.close()

    return render_template('newsletter.html', user=user, newsletters=newsletters)


@app.route('/create_newsletter', methods=['POST'])
@admin_required
def create_newsletter():
    """Create newsletter."""
    user = get_current_user()

    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO newsletters (title, content, created_by_email, created_by_name)
            VALUES (?, ?, ?, ?)
        ''', (title, content, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()

        flash('Nyhetsbrev opprettet!')
    else:
        flash('Tittel og innhold er påkrevd')

    return redirect(url_for('newsletter'))


@app.route('/send_newsletter/<int:newsletter_id>', methods=['POST'])
@admin_required
def send_newsletter(newsletter_id):
    """Send newsletter."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE newsletters SET sent_date = CURRENT_TIMESTAMP WHERE id = ?', (newsletter_id,))
    conn.commit()
    conn.close()

    flash('Nyhetsbrev sendt! (Simulert - e-postintegrasjon må implementeres)')
    return redirect(url_for('newsletter'))


@app.route('/suppliers')
@auth_required
def suppliers():
    """Suppliers page."""
    user = get_current_user()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, username, password, website
        FROM suppliers
        ORDER BY name ASC
    ''')
    suppliers_list = cursor.fetchall()

    conn.close()

    return render_template('suppliers.html', user=user, suppliers=suppliers_list)


@app.route('/add_supplier', methods=['POST'])
@auth_required
def add_supplier():
    """Add supplier."""
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    website = request.form.get('website')

    if name:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO suppliers (name, username, password, website)
            VALUES (?, ?, ?, ?)
        ''', (name, username, password, website))
        conn.commit()
        conn.close()

        flash('Leverandør lagt til!')
    else:
        flash('Leverandørnavn er påkrevd')

    return redirect(url_for('suppliers'))


@app.route('/update_supplier', methods=['POST'])
@auth_required
def update_supplier():
    """Update supplier."""
    supplier_id = request.form.get('supplier_id')
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    website = request.form.get('website')

    if supplier_id and name:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE suppliers
            SET name = ?, username = ?, password = ?, website = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, username, password, website, supplier_id))
        conn.commit()
        conn.close()

        flash('Leverandør oppdatert!')
    else:
        flash('Leverandørnavn er påkrevd')

    return redirect(url_for('suppliers'))


@app.route('/delete_supplier/<int:supplier_id>', methods=['POST'])
@auth_required
def delete_supplier(supplier_id):
    """Delete supplier."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM suppliers WHERE id = ?', (supplier_id,))
    conn.commit()
    conn.close()

    flash('Leverandør slettet!')
    return redirect(url_for('suppliers'))


@app.route('/create_post', methods=['POST'])
@auth_required
def create_post():
    """Create dashboard post."""
    user = get_current_user()

    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (user_email, user_name, title, content)
            VALUES (?, ?, ?, ?)
        ''', (user.get('mail'), user.get('displayName'), title, content))
        conn.commit()
        conn.close()

        flash('Innlegg publisert!')
    else:
        flash('Vennligst fyll ut alle felt')

    return redirect(url_for('dashboard'))


# Error handlers
@app.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized access."""
    return render_template('base.html', user=None), 401


@app.errorhandler(403)
def forbidden(error):
    """Handle forbidden access."""
    flash('Access forbidden')
    return redirect(url_for('dashboard')), 403


@app.errorhandler(404)
def not_found(error):
    """Handle not found errors."""
    user = get_current_user()
    return render_template('base.html', user=user), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    user = get_current_user()
    return render_template('base.html', user=user), 500


if __name__ == '__main__':
    init_db()
    try:
        print("Starting GRM Intranet with integrated authentication...")
        print(f"Base URL: {Config.BASE_URL}")
        print(f"Session type: {Config.SESSION_TYPE}")
        print(f"Admin users: {len(Config.ADMIN_UPNS)} configured")

        app.run(debug=True, host='0.0.0.0', port=5000)
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
    except Exception as e:
        print(f"Failed to start application: {e}")