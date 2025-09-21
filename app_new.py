from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import os
import requests
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'grm-intranet-secret-key-2023'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Authentication backend URL
AUTH_BACKEND_URL = 'http://localhost:5050'

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'salg'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'verksted'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'hms'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'it'), exist_ok=True)


def get_current_user():
    """
    Get current user from authentication backend.

    Returns:
        dict: User data if authenticated, None if not authenticated
    """
    try:
        # Call the authentication backend with the current request cookies
        response = requests.get(
            f'{AUTH_BACKEND_URL}/api/me',
            cookies=request.cookies,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        # If backend is down or unreachable, treat as not authenticated
        return None


def auth_required(f):
    """
    Decorator to require authentication for a route.
    If user is not authenticated, redirect to login.
    """
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            # Redirect to authentication backend login
            return redirect(f'{AUTH_BACKEND_URL}/auth/login')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin privileges for a route.
    """
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(f'{AUTH_BACKEND_URL}/auth/login')
        if not user.get('is_admin', False):
            flash('Admin privileges required')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def init_db():
    """Initialize database with required tables (keeping existing structure)."""
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


# Routes
@app.route('/')
def home():
    """Home page - redirect to dashboard."""
    return redirect(url_for('dashboard'))


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

    # Get all events for the current month
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

    # Get all tasks with user information
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

    # Get all newsletters
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

    # Get all suppliers ordered alphabetically
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


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)