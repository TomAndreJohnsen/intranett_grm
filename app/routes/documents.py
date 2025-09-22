import logging
import os
from typing import List, Dict, Optional
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from werkzeug.utils import secure_filename
from ..utils.helpers import auth_required, get_current_user, get_user_display_name
from ..models.db import query_db, execute_db

bp = Blueprint('documents', __name__, url_prefix='/documents')
logger = logging.getLogger(__name__)

# Tillatte filtyper
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'png', 'jpg', 'jpeg', 'gif', 'bmp',
    'zip', 'rar', '7z',
    'csv', 'json', 'xml'
}

FOLDER_NAMES = {
    'salg': '💼 Salg',
    'verksted': '🔧 Verksted',
    'hr': '👥 HR',
    'it': '💻 IT'
}

def allowed_file(filename: str) -> bool:
    """Sjekk om filtypen er tillatt"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_icon(filename: str) -> str:
    """Få ikon basert på filtype"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    icons = {
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📄',
        'xls': '📊', 'xlsx': '📊', 'csv': '📊',
        'ppt': '📋', 'pptx': '📋',
        'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'bmp': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦',
        'json': '⚙️', 'xml': '⚙️'
    }

    return icons.get(ext, '📄')

def format_file_size(size_bytes: int) -> str:
    """Format file size til human readable"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"

@bp.route('/')
@bp.route('/<folder>')
@auth_required
def index(folder: Optional[str] = None):
    """Dokumentbank hovedside"""
    user_name = get_user_display_name()
    logger.info(f"Documents accessed by {user_name}, folder: {folder}")

    try:
        # Hent dokumenter
        if folder:
            if folder not in FOLDER_NAMES:
                flash(f'Ukjent mappe: {folder}', 'error')
                return redirect(url_for('documents.index'))

            documents = query_db(
                'SELECT * FROM documents WHERE folder = ? ORDER BY uploaded_at DESC',
                (folder,)
            )
        else:
            documents = query_db(
                'SELECT * FROM documents ORDER BY uploaded_at DESC'
            )

        # Legg til metadata for hvert dokument
        for doc in documents:
            doc['icon'] = get_file_icon(doc['filename'])
            doc['size_formatted'] = format_file_size(doc.get('file_size', 0))

        # Statistikk per mappe
        folder_stats = {}
        for folder_key in FOLDER_NAMES.keys():
            count = query_db(
                'SELECT COUNT(*) as count FROM documents WHERE folder = ?',
                (folder_key,),
                one=True
            )
            folder_stats[folder_key] = count['count'] if count else 0

        return render_template('documents/index.html',
                             documents=documents,
                             current_folder=folder,
                             folders=FOLDER_NAMES,
                             folder_stats=folder_stats,
                             user_name=user_name)

    except Exception as e:
        logger.error(f"Error loading documents: {str(e)}")
        flash('Feil ved lasting av dokumenter', 'error')
        return render_template('documents/index.html',
                             documents=[],
                             current_folder=folder,
                             folders=FOLDER_NAMES,
                             folder_stats={},
                             user_name=user_name)

@bp.route('/upload', methods=['POST'])
@auth_required
def upload():
    """Last opp dokument"""
    user_name = get_user_display_name()

    if 'file' not in request.files:
        flash('Ingen fil valgt', 'error')
        return redirect(request.referrer or url_for('documents.index'))

    file = request.files['file']
    folder = request.form.get('folder', 'it')

    if file.filename == '':
        flash('Ingen fil valgt', 'error')
        return redirect(request.referrer or url_for('documents.index'))

    if folder not in FOLDER_NAMES:
        flash('Ugyldig mappe', 'error')
        return redirect(request.referrer or url_for('documents.index'))

    if not allowed_file(file.filename):
        flash(f'Filtype ikke tillatt. Tillatte typer: {", ".join(sorted(ALLOWED_EXTENSIONS))}', 'error')
        return redirect(request.referrer or url_for('documents.index'))

    try:
        # Sikker filnavn
        original_filename = file.filename
        filename = secure_filename(original_filename)

        # Sjekk at vi ikke overskriver eksisterende fil
        existing = query_db(
            'SELECT id FROM documents WHERE filename = ? AND folder = ?',
            (filename, folder),
            one=True
        )

        if existing:
            # Legg til timestamp for å unngå konflikt
            from datetime import datetime
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}{ext}"

        # Opprett mappe hvis den ikke eksisterer
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        folder_path = os.path.join(upload_folder, folder)
        os.makedirs(folder_path, exist_ok=True)

        # Lagre fil
        file_path = os.path.join(folder_path, filename)
        file.save(file_path)

        # Hent filstørrelse
        file_size = os.path.getsize(file_path)

        # Lagre metadata i database
        doc_id = execute_db(
            '''INSERT INTO documents
               (filename, original_filename, folder, uploader, file_size)
               VALUES (?, ?, ?, ?, ?)''',
            (filename, original_filename, folder, user_name, file_size)
        )

        if doc_id:
            logger.info(f"File uploaded by {user_name}: {original_filename} -> {folder}/{filename}")
            flash(f'Fil "{original_filename}" lastet opp til {FOLDER_NAMES[folder]}!', 'success')
        else:
            # Rydd opp fil hvis database feilet
            try:
                os.remove(file_path)
            except:
                pass
            flash('Feil ved lagring av fil metadata', 'error')

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        flash('Feil ved opplasting av fil', 'error')

    return redirect(url_for('documents.index', folder=folder))

@bp.route('/download/<int:doc_id>')
@auth_required
def download(doc_id: int):
    """Last ned dokument"""
    user_name = get_user_display_name()

    try:
        doc = query_db(
            'SELECT * FROM documents WHERE id = ?',
            (doc_id,),
            one=True
        )

        if not doc:
            flash('Dokument ikke funnet', 'error')
            return redirect(url_for('documents.index'))

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_path = os.path.join(upload_folder, doc['folder'], doc['filename'])

        if not os.path.exists(file_path):
            flash('Fil ikke funnet på server', 'error')
            return redirect(url_for('documents.index', folder=doc['folder']))

        logger.info(f"File downloaded by {user_name}: {doc['original_filename']}")

        return send_from_directory(
            os.path.join(upload_folder, doc['folder']),
            doc['filename'],
            as_attachment=True,
            download_name=doc['original_filename']
        )

    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        flash('Feil ved nedlasting av fil', 'error')
        return redirect(url_for('documents.index'))

@bp.route('/delete/<int:doc_id>', methods=['POST'])
@auth_required
def delete(doc_id: int):
    """Slett dokument"""
    user_name = get_user_display_name()

    try:
        doc = query_db(
            'SELECT * FROM documents WHERE id = ?',
            (doc_id,),
            one=True
        )

        if not doc:
            flash('Dokument ikke funnet', 'error')
            return redirect(url_for('documents.index'))

        # Slett fil fra disk
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        file_path = os.path.join(upload_folder, doc['folder'], doc['filename'])

        if os.path.exists(file_path):
            os.remove(file_path)

        # Slett fra database
        result = execute_db(
            'DELETE FROM documents WHERE id = ?',
            (doc_id,)
        )

        if result:
            logger.info(f"File deleted by {user_name}: {doc['original_filename']}")
            flash(f'Dokument "{doc["original_filename"]}" slettet', 'success')
        else:
            flash('Feil ved sletting av dokument', 'error')

    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        flash('Feil ved sletting av dokument', 'error')

    folder = request.form.get('folder', 'it')
    return redirect(url_for('documents.index', folder=folder))

@bp.route('/api/stats')
@auth_required
def api_stats():
    """API endpoint for dokument statistikk"""
    try:
        stats = {}
        total_size = 0
        total_files = 0

        for folder_key in FOLDER_NAMES.keys():
            folder_data = query_db(
                'SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as size FROM documents WHERE folder = ?',
                (folder_key,),
                one=True
            )

            count = folder_data['count'] if folder_data else 0
            size = folder_data['size'] if folder_data else 0

            stats[folder_key] = {
                'count': count,
                'size': size,
                'size_formatted': format_file_size(size)
            }

            total_files += count
            total_size += size

        return {
            'folders': stats,
            'total_files': total_files,
            'total_size': total_size,
            'total_size_formatted': format_file_size(total_size),
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Error fetching document stats: {str(e)}")
        return {'error': 'Failed to fetch statistics', 'status': 'error'}, 500