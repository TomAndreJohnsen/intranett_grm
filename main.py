"""
GRM Intranet Application with Microsoft Entra ID authentication.
All-in-one Flask app with working blueprints and database integration.
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
    SECRET_KEY = str(os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production'))
    CLIENT_ID = os.environ.get('MS_CLIENT_ID')
    CLIENT_SECRET = os.environ.get('MS_CLIENT_SECRET')
    TENANT_ID = os.environ.get('MS_TENANT_ID')
    BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')
    REDIRECT_URI = f"{BASE_URL}/auth/callback"
    ADMIN_UPNS = [upn.strip() for upn in os.environ.get('ADMIN_UPNS', '').split(',') if upn.strip()]
    SESSION_TYPE = str(os.environ.get('SESSION_TYPE', 'filesystem'))
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = str(os.environ.get('SESSION_KEY_PREFIX', 'intranet:'))
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = str(os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'))
    SESSION_COOKIE_NAME = str(os.environ.get('SESSION_COOKIE_NAME', 'session'))
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')
    SESSION_COOKIE_PATH = str(os.environ.get('SESSION_COOKIE_PATH', '/'))
    SESSION_FILE_THRESHOLD = int(os.environ.get('SESSION_FILE_THRESHOLD', 500))
    SCOPES = ["https://graph.microsoft.com/User.Read"]
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

    @classmethod
    def validate_config(cls):
        """Validate configuration."""
        required_vars = ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID']
        missing_vars = [f'MS_{var}' for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        return True


# Authentication Manager
class AuthManager:
    """Manages Microsoft Entra ID authentication using MSAL."""

    def __init__(self):
        self.msal_app = None
        self._initialized = False

    def _ensure_initialized(self):
        if not self._initialized:
            try:
                Config.validate_config()
                self.msal_app = msal.ConfidentialClientApplication(
                    Config.CLIENT_ID,
                    authority=Config.AUTHORITY,
                    client_credential=Config.CLIENT_SECRET
                )
                self._initialized = True
            except Exception as e:
                raise ValueError(f"Authentication configuration error: {str(e)}")

    def get_auth_url(self):
        self._ensure_initialized()
        state = str(uuid.uuid4())
        session['auth_state'] = state
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=list(Config.SCOPES),
            state=state,
            redirect_uri=Config.REDIRECT_URI
        )
        return auth_url, state

    def handle_callback(self, auth_code, state):
        self._ensure_initialized()
        if state != session.get('auth_state'):
            return None
        result = self.msal_app.acquire_token_by_authorization_code(
            auth_code,
            scopes=list(Config.SCOPES),
            redirect_uri=Config.REDIRECT_URI
        )
        if 'error' in result:
            return None
        session['access_token'] = result.get('access_token')
        session['id_token'] = result.get('id_token')
        session['user_id'] = result.get('id_token_claims', {}).get('oid')
        user_info = self.get_user_profile(result.get('access_token'))
        if user_info:
            session['user'] = user_info
            session['is_admin'] = user_info.get('userPrincipalName', '').lower() in [upn.lower() for upn in Config.ADMIN_UPNS]
        session.pop('auth_state', None)
        return user_info

    def get_user_profile(self, access_token):
        if not access_token:
            return None
        graph_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        try:
            response = requests.get(graph_url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def logout(self):
        session.clear()
        return f"{Config.AUTHORITY}/oauth2/v2.0/logout?post_logout_redirect_uri={Config.BASE_URL}"

    def is_authenticated(self):
        return 'user' in session and 'access_token' in session

    def get_current_user(self):
        if self.is_authenticated():
            user_data = session.get('user', {})
            user_data['is_admin'] = session.get('is_admin', False)
            return user_data
        return None


# Create Flask app
app = Flask(__name__, template_folder='templates')
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'database.db')

# Configure session management
if Config.SESSION_TYPE == 'redis' and os.environ.get('REDIS_URL'):
    import redis
    app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL'))
else:
    app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

Session(app)

# Create upload directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
for folder in ['salg', 'verksted', 'hms', 'it']:
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder), exist_ok=True)

# Initialize auth manager
auth_manager = AuthManager()

# Authentication decorators
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_manager.is_authenticated():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
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

def get_current_user():
    return auth_manager.get_current_user()

def get_db_connection():
    """Get database connection using configured path."""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

# Database initialization
def init_db():
    """Initialize database with all required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Posts table
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

    # Tasks table
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

    # Create default suppliers
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
    print("Database initialized successfully with all tables")


# ========== AUTHENTICATION ROUTES ==========
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
    auth_code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        flash(f'Login error: {error_description}')
        return redirect(url_for('home'))

    if not auth_code:
        flash('Missing authorization code')
        return redirect(url_for('home'))

    try:
        user_info = auth_manager.handle_callback(auth_code, state)
        if user_info:
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
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': True, 'logout_url': logout_url, 'message': 'Logged out successfully'})
        return redirect(logout_url)
    except Exception as e:
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'error': 'Logout failed', 'details': str(e)}), 500
        flash('Logout failed')
        return redirect(url_for('home'))


# ========== MAIN ROUTES ==========
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
    conn = get_db_connection()

    # Get recent newsletters
    if user.get('is_admin', False):
        newsletters = conn.execute('''
            SELECT id, title, content, sent_date, created_at, created_by_name
            FROM newsletters ORDER BY created_at DESC LIMIT 10
        ''').fetchall()
    else:
        newsletters = conn.execute('''
            SELECT id, title, content, sent_date, created_at, created_by_name
            FROM newsletters WHERE sent_date IS NOT NULL
            ORDER BY sent_date DESC LIMIT 10
        ''').fetchall()

    # Get recent tasks
    tasks = conn.execute('''
        SELECT id, title, status, priority, assigned_to_name
        FROM tasks WHERE status != 'completed'
        ORDER BY created_at DESC LIMIT 5
    ''').fetchall()

    # Get upcoming events
    events = conn.execute('''
        SELECT id, title, start_date, start_time, location, responsible_user_name
        FROM calendar_events WHERE start_date >= date('now')
        ORDER BY start_date, start_time LIMIT 5
    ''').fetchall()

    # Convert Row objects to dictionaries for JSON serialization
    newsletters_dict = [dict(newsletter) for newsletter in newsletters]
    tasks_dict = [dict(task) for task in tasks]
    events_dict = [dict(event) for event in events]

    conn.close()
    return render_template('dashboard.html', user=user, newsletters=newsletters_dict, tasks=tasks_dict, events=events_dict)


# ========== CALENDAR ROUTES ==========
@app.route('/calendar')
@app.route('/calendar/')
@auth_required
def calendar():
    """Calendar page."""
    user = get_current_user()
    conn = get_db_connection()

    events = conn.execute('''
        SELECT id, title, description, start_date, end_date,
               start_time, end_time, location, responsible_user_name
        FROM calendar_events ORDER BY start_date, start_time
    ''').fetchall()

    # Convert Row objects to dictionaries for JSON serialization
    events_dict = [dict(event) for event in events]

    conn.close()
    return render_template('calendar.html', user=user, events=events_dict)

@app.route('/calendar/create', methods=['POST'])
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
        conn = get_db_connection()
        conn.execute('''
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


# ========== DOCUMENTS ROUTES ==========
@app.route('/documents')
@app.route('/documents/')
@app.route('/documents/<folder>')
@auth_required
def documents(folder=None):
    """Documents page."""
    user = get_current_user()
    allowed_folders = ['salg', 'verksted', 'hms', 'it']

    if folder and folder not in allowed_folders:
        flash('Ugyldig mappe')
        return redirect(url_for('documents'))

    conn = get_db_connection()
    if folder:
        documents_list = conn.execute('''
            SELECT id, original_filename, filename, upload_date, uploaded_by_name
            FROM documents WHERE folder = ? ORDER BY upload_date DESC
        ''', (folder,)).fetchall()
        # Convert Row objects to dictionaries for JSON serialization
        documents_dict = [dict(doc) for doc in documents_list]
    else:
        documents_dict = []

    conn.close()
    return render_template('documents.html', user=user, current_folder=folder,
                         documents=documents_dict, folders=allowed_folders)

@app.route('/documents/upload', methods=['POST'])
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

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO documents (filename, original_filename, folder, uploaded_by_email, uploaded_by_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (unique_filename, filename, folder, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()
        flash(f'Fil "{filename}" lastet opp til {folder.title()}')

    return redirect(url_for('documents', folder=folder))

@app.route('/documents/download/<int:doc_id>')
@auth_required
def download_document(doc_id):
    """Download document."""
    conn = get_db_connection()
    doc = conn.execute('SELECT filename, original_filename, folder FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()

    if doc:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['folder'])
        return send_from_directory(file_path, doc['filename'], as_attachment=True, download_name=doc['original_filename'])
    else:
        flash('Fil ikke funnet')
        return redirect(url_for('documents'))

@app.route('/documents/delete/<int:doc_id>', methods=['POST'])
@admin_required
def delete_document(doc_id):
    """Delete document."""
    conn = get_db_connection()
    doc = conn.execute('SELECT filename, folder FROM documents WHERE id = ?', (doc_id,)).fetchone()

    if doc:
        # Delete file from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc['folder'], doc['filename'])
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            flash(f'Kunne ikke slette fil fra disk: {str(e)}')
            conn.close()
            return redirect(request.referrer or url_for('documents'))

        # Delete database record
        conn.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        flash('Dokument slettet')
    else:
        flash('Dokument ikke funnet')

    conn.close()
    return redirect(request.referrer or url_for('documents'))


# ========== TASKS ROUTES ==========
@app.route('/tasks')
@app.route('/tasks/')
@auth_required
def tasks():
    """Tasks page."""
    user = get_current_user()
    conn = get_db_connection()

    tasks_list = conn.execute('''
        SELECT id, title, description, status, priority, department,
               created_at, created_by_name, assigned_to_name
        FROM tasks ORDER BY
            CASE status WHEN 'todo' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'completed' THEN 3 END,
            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
            created_at DESC
    ''').fetchall()

    # Convert Row objects to dictionaries for JSON serialization
    tasks_dict = [dict(task) for task in tasks_list]

    conn.close()
    return render_template('tasks.html', user=user, tasks=tasks_dict)

@app.route('/tasks/create', methods=['POST'])
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
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO tasks (title, description, priority, department, assigned_to_name, created_by_email, created_by_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, priority, department, assigned_to or None, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()
        flash('Oppgave opprettet!')
    else:
        flash('Tittel er påkrevd')

    return redirect(url_for('tasks'))

@app.route('/tasks/update', methods=['POST'])
@auth_required
def update_task_status():
    """Update task status."""
    task_id = request.form.get('task_id')
    new_status = request.form.get('status')

    if task_id and new_status in ['todo', 'in_progress', 'completed']:
        conn = get_db_connection()
        conn.execute('UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_status, task_id))
        conn.commit()
        conn.close()
        flash('Oppgavestatus oppdatert!')
    else:
        flash('Ugyldig oppgave eller status')

    return redirect(url_for('tasks'))


# ========== SUPPLIERS ROUTES ==========
@app.route('/suppliers')
@app.route('/suppliers/')
@auth_required
def suppliers():
    """Suppliers page."""
    user = get_current_user()
    conn = get_db_connection()
    suppliers_list = conn.execute('SELECT id, name, username, password, website FROM suppliers ORDER BY name ASC').fetchall()

    # Convert Row objects to dictionaries for JSON serialization
    suppliers_dict = [dict(supplier) for supplier in suppliers_list]

    conn.close()
    return render_template('suppliers.html', user=user, suppliers=suppliers_dict)

@app.route('/suppliers/add', methods=['POST'])
@auth_required
def add_supplier():
    """Add supplier."""
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    website = request.form.get('website')

    if name:
        conn = get_db_connection()
        conn.execute('INSERT INTO suppliers (name, username, password, website) VALUES (?, ?, ?, ?)',
                    (name, username, password, website))
        conn.commit()
        conn.close()
        flash('Leverandør lagt til!')
    else:
        flash('Leverandørnavn er påkrevd')

    return redirect(url_for('suppliers'))

@app.route('/suppliers/update', methods=['POST'])
@auth_required
def update_supplier():
    """Update supplier."""
    supplier_id = request.form.get('supplier_id')
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    website = request.form.get('website')

    if supplier_id and name:
        conn = get_db_connection()
        conn.execute('''UPDATE suppliers SET name = ?, username = ?, password = ?, website = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?''',
                    (name, username, password, website, supplier_id))
        conn.commit()
        conn.close()
        flash('Leverandør oppdatert!')
    else:
        flash('Leverandørnavn er påkrevd')

    return redirect(url_for('suppliers'))

@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@auth_required
def delete_supplier(supplier_id):
    """Delete supplier."""
    conn = get_db_connection()
    conn.execute('DELETE FROM suppliers WHERE id = ?', (supplier_id,))
    conn.commit()
    conn.close()
    flash('Leverandør slettet!')
    return redirect(url_for('suppliers'))


# ========== NEWSLETTER ROUTES ==========
@app.route('/newsletter')
@app.route('/newsletter/')
@auth_required
def newsletter():
    """Newsletter page."""
    user = get_current_user()
    conn = get_db_connection()
    newsletters = conn.execute('SELECT id, title, content, sent_date, created_at, created_by_name FROM newsletters ORDER BY created_at DESC').fetchall()

    # Convert Row objects to dictionaries for JSON serialization
    newsletters_dict = [dict(newsletter) for newsletter in newsletters]

    conn.close()
    return render_template('newsletter.html', user=user, newsletters=newsletters_dict)

@app.route('/newsletter/create', methods=['POST'])
@admin_required
def create_newsletter():
    """Create newsletter."""
    user = get_current_user()
    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = get_db_connection()
        conn.execute('INSERT INTO newsletters (title, content, created_by_email, created_by_name) VALUES (?, ?, ?, ?)',
                    (title, content, user.get('mail'), user.get('displayName')))
        conn.commit()
        conn.close()
        flash('Nyhetsbrev opprettet!')
    else:
        flash('Tittel og innhold er påkrevd')

    return redirect(url_for('newsletter'))

@app.route('/newsletter/send/<int:newsletter_id>', methods=['POST'])
@admin_required
def send_newsletter(newsletter_id):
    """Send newsletter."""
    conn = get_db_connection()
    conn.execute('UPDATE newsletters SET sent_date = CURRENT_TIMESTAMP WHERE id = ?', (newsletter_id,))
    conn.commit()
    conn.close()
    flash('Nyhetsbrev sendt! (Simulert - e-postintegrasjon må implementeres)')
    return redirect(url_for('newsletter'))


# ========== API ROUTES ==========
@app.route('/api/me')
def api_me():
    """Get current user information."""
    try:
        user_info = auth_manager.get_current_user()
        if user_info:
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


# ========== DASHBOARD POSTS ==========
@app.route('/posts/create', methods=['POST'])
@auth_required
def create_post():
    """Create dashboard post."""
    user = get_current_user()
    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (user_email, user_name, title, content) VALUES (?, ?, ?, ?)',
                    (user.get('mail'), user.get('displayName'), title, content))
        conn.commit()
        conn.close()
        flash('Innlegg publisert!')
    else:
        flash('Vennligst fyll ut alle felt')

    return redirect(url_for('dashboard'))


# ========== ERROR HANDLERS ==========
@app.errorhandler(401)
def unauthorized(error):
    return render_template('base.html', user=None), 401

@app.errorhandler(403)
def forbidden(error):
    flash('Access forbidden')
    return redirect(url_for('dashboard')), 403

@app.errorhandler(404)
def not_found(error):
    user = get_current_user()
    return render_template('base.html', user=user), 404

@app.errorhandler(500)
def internal_error(error):
    user = get_current_user()
    return render_template('base.html', user=user), 500


if __name__ == '__main__':
    init_db()
    try:
        print("=" * 50)
        print("🚀 Starting GRM Intranet Application")
        print("=" * 50)
        print(f"📂 Database: {app.config['DATABASE_PATH']}")
        print(f"🌐 Base URL: {Config.BASE_URL}")
        print(f"💾 Session type: {Config.SESSION_TYPE}")
        print(f"👥 Admin users: {len(Config.ADMIN_UPNS)} configured")
        print("=" * 50)
        print("📋 Available Routes:")
        print("   /dashboard     - Main dashboard")
        print("   /calendar      - Calendar management")
        print("   /documents     - Document management")
        print("   /tasks         - Task management")
        print("   /suppliers     - Supplier management")
        print("   /newsletter    - Newsletter management")
        print("   /auth/login    - Microsoft login")
        print("=" * 50)

        app.run(debug=True, host='0.0.0.0', port=5000)

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
    except Exception as e:
        print(f"❌ Failed to start application: {e}")