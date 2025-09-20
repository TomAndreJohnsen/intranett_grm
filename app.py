from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'grm-intranet-secret-key-2023'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'salg'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'verksted'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'hr'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'it'), exist_ok=True)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email, name, role):
        self.id = id
        self.email = email
        self.name = name
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        return User(user_data[0], user_data[1], user_data[2], user_data[4])
    return None

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Posts table (newsfeed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Comments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            folder TEXT NOT NULL,
            uploaded_by INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users (id)
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
            responsible_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (responsible_user_id) REFERENCES users (id)
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
            assigned_to INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # Newsletter table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            sent_date TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # Create default admin user if not exists
    cursor.execute('SELECT * FROM users WHERE email = ?', ('admin@grm.no',))
    if not cursor.fetchone():
        admin_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (email, name, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('admin@grm.no', 'Administrator', admin_password, 'admin'))

    conn.commit()
    conn.close()

# Routes
@app.route('/')
@login_required
def dashboard():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get recent posts with user names
    cursor.execute('''
        SELECT p.id, p.title, p.content, p.created_at, u.name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
        LIMIT 10
    ''')
    posts = cursor.fetchall()

    # Get recent tasks
    cursor.execute('''
        SELECT t.id, t.title, t.status, t.priority, u.name as assigned_to
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.status != 'completed'
        ORDER BY t.created_at DESC
        LIMIT 5
    ''')
    tasks = cursor.fetchall()

    # Get upcoming calendar events
    cursor.execute('''
        SELECT c.id, c.title, c.start_date, c.start_time, c.location, u.name as responsible
        FROM calendar_events c
        LEFT JOIN users u ON c.responsible_user_id = u.id
        WHERE c.start_date >= date('now')
        ORDER BY c.start_date, c.start_time
        LIMIT 5
    ''')
    events = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html', posts=posts, tasks=tasks, events=events)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data and check_password_hash(user_data[3], password):
            user = User(user_data[0], user_data[1], user_data[2], user_data[4])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Ugyldig e-post eller passord')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO posts (user_id, title, content)
            VALUES (?, ?, ?)
        ''', (current_user.id, title, content))
        conn.commit()
        conn.close()

        flash('Innlegg publisert!')
    else:
        flash('Vennligst fyll ut alle felt')

    return redirect(url_for('dashboard'))

@app.route('/documents')
@app.route('/documents/<folder>')
@login_required
def documents(folder=None):
    allowed_folders = ['salg', 'verksted', 'hr', 'it']
    if folder and folder not in allowed_folders:
        flash('Ugyldig mappe')
        return redirect(url_for('documents'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if folder:
        cursor.execute('''
            SELECT d.id, d.original_filename, d.filename, d.upload_date, u.name
            FROM documents d
            JOIN users u ON d.uploaded_by = u.id
            WHERE d.folder = ?
            ORDER BY d.upload_date DESC
        ''', (folder,))
        documents_list = cursor.fetchall()
    else:
        documents_list = []

    conn.close()

    return render_template('documents.html',
                         current_folder=folder,
                         documents=documents_list,
                         folders=allowed_folders)

@app.route('/upload_document', methods=['POST'])
@login_required
def upload_document():
    if 'file' not in request.files:
        flash('Ingen fil valgt')
        return redirect(request.referrer)

    file = request.files['file']
    folder = request.form.get('folder')

    if file.filename == '' or not folder:
        flash('Vennligst velg fil og mappe')
        return redirect(request.referrer)

    if folder not in ['salg', 'verksted', 'hr', 'it']:
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
            INSERT INTO documents (filename, original_filename, folder, uploaded_by)
            VALUES (?, ?, ?, ?)
        ''', (unique_filename, filename, folder, current_user.id))
        conn.commit()
        conn.close()

        flash(f'Fil "{filename}" lastet opp til {folder.title()}')

    return redirect(url_for('documents', folder=folder))

@app.route('/download/<int:doc_id>')
@login_required
def download_document(doc_id):
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
@login_required
def calendar():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get all events for the current month
    cursor.execute('''
        SELECT c.id, c.title, c.description, c.start_date, c.end_date,
               c.start_time, c.end_time, c.location, u.name as responsible
        FROM calendar_events c
        LEFT JOIN users u ON c.responsible_user_id = u.id
        ORDER BY c.start_date, c.start_time
    ''')
    events = cursor.fetchall()

    conn.close()

    return render_template('calendar.html', events=events)

@app.route('/create_event', methods=['POST'])
@login_required
def create_event():
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
            (title, description, start_date, end_date, start_time, end_time, location, responsible_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, start_date, end_date, start_time, end_time, location, current_user.id))
        conn.commit()
        conn.close()

        flash('Hendelse opprettet!')
    else:
        flash('Tittel og startdato er påkrevd')

    return redirect(url_for('calendar'))

@app.route('/tasks')
@login_required
def tasks():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get all tasks with user information
    cursor.execute('''
        SELECT t.id, t.title, t.description, t.status, t.priority, t.department,
               t.created_at, u1.name as created_by, u2.name as assigned_to
        FROM tasks t
        JOIN users u1 ON t.created_by = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
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

    # Get all users for assignment dropdown
    cursor.execute('SELECT id, name FROM users ORDER BY name')
    users = cursor.fetchall()

    conn.close()

    return render_template('tasks.html', tasks=tasks_list, users=users)

@app.route('/create_task', methods=['POST'])
@login_required
def create_task():
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority', 'medium')
    department = request.form.get('department')
    assigned_to = request.form.get('assigned_to')

    if title:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, department, assigned_to, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, priority, department, assigned_to if assigned_to else None, current_user.id))
        conn.commit()
        conn.close()

        flash('Oppgave opprettet!')
    else:
        flash('Tittel er påkrevd')

    return redirect(url_for('tasks'))

@app.route('/update_task_status', methods=['POST'])
@login_required
def update_task_status():
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
@login_required
def newsletter():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Get all newsletters
    cursor.execute('''
        SELECT n.id, n.title, n.content, n.sent_date, n.created_at, u.name as created_by
        FROM newsletters n
        JOIN users u ON n.created_by = u.id
        ORDER BY n.created_at DESC
    ''')
    newsletters = cursor.fetchall()

    conn.close()

    return render_template('newsletter.html', newsletters=newsletters)

@app.route('/create_newsletter', methods=['POST'])
@login_required
def create_newsletter():
    if current_user.role != 'admin':
        flash('Kun administratorer kan opprette nyhetsbrev')
        return redirect(url_for('newsletter'))

    title = request.form.get('title')
    content = request.form.get('content')

    if title and content:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO newsletters (title, content, created_by)
            VALUES (?, ?, ?)
        ''', (title, content, current_user.id))
        conn.commit()
        conn.close()

        flash('Nyhetsbrev opprettet!')
    else:
        flash('Tittel og innhold er påkrevd')

    return redirect(url_for('newsletter'))

@app.route('/send_newsletter/<int:newsletter_id>', methods=['POST'])
@login_required
def send_newsletter(newsletter_id):
    if current_user.role != 'admin':
        flash('Kun administratorer kan sende nyhetsbrev')
        return redirect(url_for('newsletter'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE newsletters SET sent_date = CURRENT_TIMESTAMP WHERE id = ?', (newsletter_id,))
    conn.commit()
    conn.close()

    flash('Nyhetsbrev sendt! (Simulert - e-postintegrasjon må implementeres)')
    return redirect(url_for('newsletter'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)