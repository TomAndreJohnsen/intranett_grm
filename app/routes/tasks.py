import logging
from typing import List, Dict, Optional
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..utils.helpers import auth_required, get_current_user, get_user_display_name
from ..models.db import query_db, execute_db

bp = Blueprint('tasks', __name__, url_prefix='/tasks')
logger = logging.getLogger(__name__)

# Task statuses for Kanban board
TASK_STATUSES = {
    'todo': '📋 Å gjøre',
    'in_progress': '⏳ Pågår',
    'done': '✅ Ferdig'
}

# Task priorities
TASK_PRIORITIES = {
    'low': '🟢 Lav',
    'medium': '🟡 Medium',
    'high': '🔴 Høy',
    'critical': '🔥 Kritisk'
}

@bp.route('/')
@auth_required
def index():
    """Tasks hovedside med Kanban-board"""
    user_name = get_user_display_name()
    logger.info(f"Tasks accessed by {user_name}")

    try:
        # Hent alle oppgaver gruppert etter status
        tasks_by_status = {}
        for status_key in TASK_STATUSES.keys():
            tasks = query_db(
                'SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at ASC',
                (status_key,)
            )
            tasks_by_status[status_key] = tasks

        # Hent statistikk
        total_tasks = query_db(
            'SELECT COUNT(*) as count FROM tasks',
            one=True
        )

        # Beregn statistikk per status
        stats = {}
        for status_key in TASK_STATUSES.keys():
            count = query_db(
                'SELECT COUNT(*) as count FROM tasks WHERE status = ?',
                (status_key,),
                one=True
            )
            stats[status_key] = count['count'] if count else 0

        stats['total'] = total_tasks['count'] if total_tasks else 0

        return render_template('tasks/index.html',
                             tasks_by_status=tasks_by_status,
                             task_statuses=TASK_STATUSES,
                             task_priorities=TASK_PRIORITIES,
                             stats=stats,
                             user_name=user_name)

    except Exception as e:
        logger.error(f"Error loading tasks: {str(e)}")
        flash('Feil ved lasting av oppgaver', 'error')
        return render_template('tasks/index.html',
                             tasks_by_status={status: [] for status in TASK_STATUSES.keys()},
                             task_statuses=TASK_STATUSES,
                             task_priorities=TASK_PRIORITIES,
                             stats={status: 0 for status in TASK_STATUSES.keys()},
                             user_name=user_name)

@bp.route('/create', methods=['POST'])
@auth_required
def create_task():
    """Opprett ny oppgave"""
    user_name = get_user_display_name()

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium').strip()
    assigned_to = request.form.get('assigned_to', '').strip()
    due_date = request.form.get('due_date', '').strip()

    if not title:
        flash('Tittel er påkrevd', 'error')
        return redirect(url_for('tasks.index'))

    if priority not in TASK_PRIORITIES:
        priority = 'medium'

    try:
        task_id = execute_db(
            '''INSERT INTO tasks
               (title, description, status, priority, assigned_to, due_date, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (title, description, 'todo', priority, assigned_to or None, due_date or None, user_name)
        )

        if task_id:
            logger.info(f"Task created by {user_name}: {title}")
            flash(f'Oppgave "{title}" opprettet!', 'success')
        else:
            flash('Feil ved opprettelse av oppgave', 'error')

    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        flash('Feil ved opprettelse av oppgave', 'error')

    return redirect(url_for('tasks.index'))

@bp.route('/update_status/<int:task_id>', methods=['POST'])
@auth_required
def update_task_status(task_id: int):
    """Oppdater oppgavestatus (for Kanban drag-and-drop)"""
    user_name = get_user_display_name()

    new_status = request.form.get('status', '').strip()

    if new_status not in TASK_STATUSES:
        return jsonify({'error': 'Invalid status', 'status': 'error'}), 400

    try:
        # Sjekk at oppgaven eksisterer
        task = query_db(
            'SELECT title FROM tasks WHERE id = ?',
            (task_id,),
            one=True
        )

        if not task:
            return jsonify({'error': 'Task not found', 'status': 'error'}), 404

        result = execute_db(
            'UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (new_status, task_id)
        )

        if result:
            logger.info(f"Task status updated by {user_name}: {task['title']} -> {new_status}")
            return jsonify({'message': 'Status updated', 'status': 'success'})
        else:
            return jsonify({'error': 'Failed to update status', 'status': 'error'}), 500

    except Exception as e:
        logger.error(f"Error updating task status: {str(e)}")
        return jsonify({'error': 'Failed to update status', 'status': 'error'}), 500

@bp.route('/edit/<int:task_id>', methods=['POST'])
@auth_required
def edit_task(task_id: int):
    """Rediger oppgave"""
    user_name = get_user_display_name()

    try:
        # Sjekk at oppgaven eksisterer
        task = query_db(
            'SELECT * FROM tasks WHERE id = ?',
            (task_id,),
            one=True
        )

        if not task:
            flash('Oppgave ikke funnet', 'error')
            return redirect(url_for('tasks.index'))

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium').strip()
        assigned_to = request.form.get('assigned_to', '').strip()
        due_date = request.form.get('due_date', '').strip()

        if not title:
            flash('Tittel er påkrevd', 'error')
            return redirect(url_for('tasks.index'))

        if priority not in TASK_PRIORITIES:
            priority = 'medium'

        result = execute_db(
            '''UPDATE tasks
               SET title = ?, description = ?, priority = ?, assigned_to = ?,
                   due_date = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (title, description, priority, assigned_to or None, due_date or None, task_id)
        )

        if result:
            logger.info(f"Task updated by {user_name}: {title} (ID: {task_id})")
            flash(f'Oppgave "{title}" oppdatert!', 'success')
        else:
            flash('Feil ved oppdatering av oppgave', 'error')

    except Exception as e:
        logger.error(f"Error updating task: {str(e)}")
        flash('Feil ved oppdatering av oppgave', 'error')

    return redirect(url_for('tasks.index'))

@bp.route('/delete/<int:task_id>', methods=['POST'])
@auth_required
def delete_task(task_id: int):
    """Slett oppgave"""
    user_name = get_user_display_name()

    try:
        # Hent oppgave info før sletting
        task = query_db(
            'SELECT title FROM tasks WHERE id = ?',
            (task_id,),
            one=True
        )

        if not task:
            flash('Oppgave ikke funnet', 'error')
            return redirect(url_for('tasks.index'))

        result = execute_db(
            'DELETE FROM tasks WHERE id = ?',
            (task_id,)
        )

        if result:
            logger.info(f"Task deleted by {user_name}: {task['title']} (ID: {task_id})")
            flash(f'Oppgave "{task["title"]}" slettet', 'success')
        else:
            flash('Feil ved sletting av oppgave', 'error')

    except Exception as e:
        logger.error(f"Error deleting task: {str(e)}")
        flash('Feil ved sletting av oppgave', 'error')

    return redirect(url_for('tasks.index'))

@bp.route('/api/tasks')
@auth_required
def api_tasks():
    """API endpoint for oppgaver"""
    try:
        status_filter = request.args.get('status')
        priority_filter = request.args.get('priority')

        query = 'SELECT * FROM tasks WHERE 1=1'
        params = []

        if status_filter and status_filter in TASK_STATUSES:
            query += ' AND status = ?'
            params.append(status_filter)

        if priority_filter and priority_filter in TASK_PRIORITIES:
            query += ' AND priority = ?'
            params.append(priority_filter)

        query += ' ORDER BY priority DESC, created_at ASC'

        tasks = query_db(query, params)

        return jsonify({
            'tasks': tasks,
            'count': len(tasks),
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch tasks',
            'status': 'error'
        }), 500

@bp.route('/api/stats')
@auth_required
def api_stats():
    """API endpoint for oppgave statistikk"""
    try:
        stats = {}
        total_tasks = 0

        for status_key in TASK_STATUSES.keys():
            count = query_db(
                'SELECT COUNT(*) as count FROM tasks WHERE status = ?',
                (status_key,),
                one=True
            )
            count_value = count['count'] if count else 0
            stats[status_key] = count_value
            total_tasks += count_value

        stats['total'] = total_tasks

        return jsonify({
            'stats': stats,
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching task stats: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch statistics',
            'status': 'error'
        }), 500

def get_priority_color(priority: str) -> str:
    """Få farge basert på prioritet"""
    colors = {
        'low': '#10B981',
        'medium': '#F59E0B',
        'high': '#DC2626',
        'critical': '#7C2D12'
    }
    return colors.get(priority, '#6B7280')

def get_priority_icon(priority: str) -> str:
    """Få ikon basert på prioritet"""
    icons = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🔴',
        'critical': '🔥'
    }
    return icons.get(priority, '⚪')

# Legg til hjelpefunksjoner i template context
@bp.app_template_global()
def priority_color(priority):
    return get_priority_color(priority)

@bp.app_template_global()
def priority_icon(priority):
    return get_priority_icon(priority)