import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from flask import g, current_app

logger = logging.getLogger(__name__)

def get_db():
    """Få database connection"""
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        logger.debug(f"Database connection opened: {db_path}")
    return g.db

def close_db(e=None):
    """Lukk database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()
        logger.debug("Database connection closed")

def query_db(query: str, args: tuple = (), one: bool = False) -> Union[List[Dict], Dict, None]:
    """
    Wrapper for database queries - mye enklere å bruke

    Args:
        query: SQL query string
        args: Query parameters
        one: Return single result instead of list

    Returns:
        List of dicts, single dict if one=True, or None/empty list on error
    """
    try:
        logger.debug(f"Executing query: {query[:50]}...")
        cur = get_db().execute(query, args)
        rv = cur.fetchall()
        cur.close()
        result = [dict(row) for row in rv]
        logger.debug(f"Query returned {len(result)} rows")

        if one:
            return result[0] if result else None
        return result

    except sqlite3.Error as e:
        logger.error(f"Database query error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Args: {args}")
        return None if one else []

def execute_db(query: str, args: tuple = ()) -> Optional[int]:
    """
    Execute INSERT/UPDATE/DELETE og returner lastrowid

    Args:
        query: SQL query string
        args: Query parameters

    Returns:
        lastrowid for INSERT, rowcount for UPDATE/DELETE, None on error
    """
    try:
        logger.debug(f"Executing: {query[:50]}...")
        db = get_db()
        cur = db.execute(query, args)
        db.commit()

        result = cur.lastrowid if cur.lastrowid else cur.rowcount
        logger.info(f"Database operation successful, result: {result}")
        return result

    except sqlite3.Error as e:
        logger.error(f"Database execute error: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Args: {args}")
        return None

def init_db():
    """Initialiser database med alle nødvendige tabeller"""
    logger.info("Initializing database...")
    db = get_db()

    try:
        # Users table
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Posts table (for dashboard feed)
        db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Comments table
        db.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts (id)
            )
        ''')

        # Documents table
        db.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                folder TEXT NOT NULL,
                uploader TEXT NOT NULL,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Calendar events table
        db.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                event_date DATE NOT NULL,
                event_time TIME,
                location TEXT,
                responsible TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tasks table
        db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'todo',
                priority TEXT DEFAULT 'medium',
                department TEXT DEFAULT 'general',
                assigned_to TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Newsletters table
        db.execute('''
            CREATE TABLE IF NOT EXISTS newsletters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP
            )
        ''')

        # Suppliers table
        db.execute('''
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT,
                password TEXT,
                website TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        db.commit()
        logger.info("Database tables created successfully")

        # Add sample data if database is empty
        _add_sample_data()

    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def _add_sample_data():
    """Add sample data if database is empty"""
    # Check if we already have data
    posts_count = query_db('SELECT COUNT(*) as count FROM posts', one=True)
    if posts_count and posts_count['count'] > 0:
        logger.debug("Sample data already exists")
        return

    logger.info("Adding sample data...")

    # Sample posts
    sample_posts = [
        {
            'content': 'Velkommen til det nye GRM intranett! 🎉 Her kan dere dele nyheter, oppdateringer og samarbeide bedre.',
            'author_name': 'Admin',
            'author_email': 'admin@grm.no'
        },
        {
            'content': 'Husk på sikkerhetsmøtet i morgen kl 14:00 i møterom A. Alle ansatte må delta.',
            'author_name': 'HR Avdeling',
            'author_email': 'hr@grm.no'
        },
        {
            'content': 'IT-systemene vil være nede for vedlikehold på søndag mellom 02:00 og 06:00.',
            'author_name': 'IT Support',
            'author_email': 'it@grm.no'
        }
    ]

    for post in sample_posts:
        execute_db(
            'INSERT INTO posts (content, author_name, author_email) VALUES (?, ?, ?)',
            (post['content'], post['author_name'], post['author_email'])
        )

    # Sample calendar events
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)
    next_week = date.today() + timedelta(days=7)

    sample_events = [
        {
            'title': 'Sikkerhetsmøte',
            'description': 'Månedlig sikkerhetsmøte for alle ansatte',
            'event_date': tomorrow.strftime('%Y-%m-%d'),
            'event_time': '14:00',
            'location': 'Møterom A',
            'responsible': 'HR Avdeling'
        },
        {
            'title': 'Prosjektmøte - Kunde XYZ',
            'description': 'Oppfølging av prosjekt for kunde XYZ',
            'event_date': next_week.strftime('%Y-%m-%d'),
            'event_time': '10:00',
            'location': 'Møterom B',
            'responsible': 'Prosjektleder'
        }
    ]

    for event in sample_events:
        execute_db(
            '''INSERT INTO calendar_events
               (title, description, event_date, event_time, location, responsible)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (event['title'], event['description'], event['event_date'],
             event['event_time'], event['location'], event['responsible'])
        )

    # Sample tasks
    sample_tasks = [
        {
            'title': 'Oppdater sikkerhetsrutiner',
            'description': 'Gjennomgå og oppdater alle sikkerhetsrutiner',
            'status': 'todo',
            'priority': 'high',
            'department': 'hr',
            'created_by': 'Admin'
        },
        {
            'title': 'Installler ny programvare',
            'description': 'Installer siste versjon av CAD-programvare',
            'status': 'in_progress',
            'priority': 'medium',
            'department': 'it',
            'created_by': 'IT Support'
        }
    ]

    for task in sample_tasks:
        execute_db(
            '''INSERT INTO tasks
               (title, description, status, priority, department, created_by)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (task['title'], task['description'], task['status'],
             task['priority'], task['department'], task['created_by'])
        )

    # Sample suppliers
    sample_suppliers = [
        {
            'name': 'Autoparts AS',
            'username': 'grm_kunde',
            'password': 'SecurePass123!',
            'website': 'https://autoparts.no',
            'created_by': 'Admin'
        },
        {
            'name': 'Bilgrossisten',
            'username': 'grm_account',
            'password': 'BilPass2024',
            'website': 'https://bilgrossisten.no',
            'created_by': 'Admin'
        },
        {
            'name': 'Euromaster Norge',
            'username': 'grm.kunde',
            'password': 'EuroM@ster789',
            'website': 'https://euromaster.no',
            'created_by': 'Admin'
        },
        {
            'name': 'Mekonomen',
            'username': 'grm_bedrift',
            'password': 'MekoPass456!',
            'website': 'https://mekonomen.no',
            'created_by': 'Admin'
        }
    ]

    for supplier in sample_suppliers:
        execute_db(
            '''INSERT INTO suppliers
               (name, username, password, website, created_by)
               VALUES (?, ?, ?, ?, ?)''',
            (supplier['name'], supplier['username'], supplier['password'],
             supplier['website'], supplier['created_by'])
        )

    logger.info("Sample data added successfully")

# Helper functions for specific operations

def get_posts(limit: int = 20) -> List[Dict]:
    """Hent posts for dashboard feed"""
    logger.debug(f"Fetching {limit} posts")
    return query_db(
        'SELECT * FROM posts ORDER BY created_at DESC LIMIT ?',
        (limit,)
    )

def create_post(content: str, author_name: str, author_email: str) -> Optional[int]:
    """Opprett nytt innlegg"""
    logger.info(f"Creating post by {author_name}")
    return execute_db(
        'INSERT INTO posts (content, author_name, author_email) VALUES (?, ?, ?)',
        (content, author_name, author_email)
    )

def get_recent_events(limit: int = 5) -> List[Dict]:
    """Hent kommende kalenderhendelser"""
    logger.debug(f"Fetching {limit} recent events")
    return query_db(
        '''SELECT * FROM calendar_events
           WHERE event_date >= date('now')
           ORDER BY event_date ASC, event_time ASC
           LIMIT ?''',
        (limit,)
    )

def get_task_summary() -> Dict[str, int]:
    """Hent sammendrag av oppgaver per status"""
    tasks = query_db('SELECT status, COUNT(*) as count FROM tasks GROUP BY status')

    summary = {'todo': 0, 'in_progress': 0, 'done': 0}
    for task in tasks:
        status = task.get('status', 'todo')
        if status in summary:
            summary[status] = task['count']

    logger.debug(f"Task summary: {summary}")
    return summary

def get_documents_count() -> int:
    """Hent antall dokumenter"""
    result = query_db('SELECT COUNT(*) as count FROM documents', one=True)
    return result['count'] if result else 0

def get_user_stats() -> Dict[str, Any]:
    """Hent brukerstatistikk for dashboard"""
    stats = {
        'total_posts': query_db('SELECT COUNT(*) as count FROM posts', one=True)['count'],
        'total_events': query_db('SELECT COUNT(*) as count FROM calendar_events', one=True)['count'],
        'total_tasks': query_db('SELECT COUNT(*) as count FROM tasks', one=True)['count'],
        'total_documents': get_documents_count()
    }

    logger.debug(f"User stats: {stats}")
    return stats

def get_suppliers() -> List[Dict]:
    """Hent alle leverandører sortert alfabetisk"""
    logger.debug("Fetching suppliers")
    return query_db(
        'SELECT * FROM suppliers ORDER BY name ASC'
    )

def create_supplier(name: str, username: str, password: str, website: str, created_by: str) -> Optional[int]:
    """Opprett ny leverandør"""
    logger.info(f"Creating supplier: {name}")
    return execute_db(
        '''INSERT INTO suppliers (name, username, password, website, created_by)
           VALUES (?, ?, ?, ?, ?)''',
        (name, username, password, website, created_by)
    )

def update_supplier(supplier_id: int, name: str, username: str, password: str, website: str) -> bool:
    """Oppdater leverandør"""
    logger.info(f"Updating supplier ID: {supplier_id}")
    result = execute_db(
        '''UPDATE suppliers
           SET name = ?, username = ?, password = ?, website = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (name, username, password, website, supplier_id)
    )
    return result is not None and result > 0

def delete_supplier(supplier_id: int) -> bool:
    """Slett leverandør"""
    logger.info(f"Deleting supplier ID: {supplier_id}")
    result = execute_db(
        'DELETE FROM suppliers WHERE id = ?',
        (supplier_id,)
    )
    return result is not None and result > 0

def get_supplier_by_id(supplier_id: int) -> Optional[Dict]:
    """Hent leverandør etter ID"""
    logger.debug(f"Fetching supplier ID: {supplier_id}")
    return query_db(
        'SELECT * FROM suppliers WHERE id = ?',
        (supplier_id,),
        one=True
    )