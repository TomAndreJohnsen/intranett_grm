import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..utils.helpers import auth_required, get_current_user, get_user_display_name
from ..models.db import query_db, execute_db

bp = Blueprint('calendar', __name__, url_prefix='/calendar')
logger = logging.getLogger(__name__)

@bp.route('/')
@auth_required
def index():
    """Kalender hovedside"""
    user_name = get_user_display_name()
    logger.info(f"Calendar accessed by {user_name}")

    try:
        # Hent hendelser for neste 30 dager
        today = datetime.now().date()
        end_date = today + timedelta(days=30)

        events = query_db(
            '''SELECT * FROM calendar_events
               WHERE event_date >= ? AND event_date <= ?
               ORDER BY event_date ASC, event_time ASC''',
            (today.isoformat(), end_date.isoformat())
        )

        # Hent statistikk
        total_events = query_db(
            'SELECT COUNT(*) as count FROM calendar_events',
            one=True
        )

        upcoming_events = query_db(
            'SELECT COUNT(*) as count FROM calendar_events WHERE event_date >= ?',
            (today.isoformat(),),
            one=True
        )

        stats = {
            'total_events': total_events['count'] if total_events else 0,
            'upcoming_events': upcoming_events['count'] if upcoming_events else 0
        }

        return render_template('calendar/index.html',
                             events=events,
                             stats=stats,
                             user_name=user_name)

    except Exception as e:
        logger.error(f"Error loading calendar: {str(e)}")
        flash('Feil ved lasting av kalender', 'error')
        return render_template('calendar/index.html',
                             events=[],
                             stats={'total_events': 0, 'upcoming_events': 0},
                             user_name=user_name)

@bp.route('/create', methods=['POST'])
@auth_required
def create_event():
    """Opprett ny hendelse"""
    user_name = get_user_display_name()

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    event_date = request.form.get('event_date', '').strip()
    event_time = request.form.get('event_time', '').strip()
    location = request.form.get('location', '').strip()
    event_type = request.form.get('event_type', 'meeting').strip()

    if not title:
        flash('Tittel er påkrevd', 'error')
        return redirect(url_for('calendar.index'))

    if not event_date:
        flash('Dato er påkrevd', 'error')
        return redirect(url_for('calendar.index'))

    try:
        # Valider dato format
        datetime.strptime(event_date, '%Y-%m-%d')

        # Valider tid hvis oppgitt
        if event_time:
            datetime.strptime(event_time, '%H:%M')

        event_id = execute_db(
            '''INSERT INTO calendar_events
               (title, description, event_date, event_time, location, event_type, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (title, description, event_date, event_time or None, location or None, event_type, user_name)
        )

        if event_id:
            logger.info(f"Event created by {user_name}: {title} on {event_date}")
            flash(f'Hendelse "{title}" opprettet!', 'success')
        else:
            flash('Feil ved opprettelse av hendelse', 'error')

    except ValueError as e:
        logger.error(f"Date validation error: {str(e)}")
        flash('Ugyldig dato eller klokkeslett format', 'error')
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        flash('Feil ved opprettelse av hendelse', 'error')

    return redirect(url_for('calendar.index'))

@bp.route('/edit/<int:event_id>', methods=['POST'])
@auth_required
def edit_event(event_id: int):
    """Rediger hendelse"""
    user_name = get_user_display_name()

    try:
        # Sjekk at hendelsen eksisterer
        event = query_db(
            'SELECT * FROM calendar_events WHERE id = ?',
            (event_id,),
            one=True
        )

        if not event:
            flash('Hendelse ikke funnet', 'error')
            return redirect(url_for('calendar.index'))

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        location = request.form.get('location', '').strip()
        event_type = request.form.get('event_type', 'meeting').strip()

        if not title or not event_date:
            flash('Tittel og dato er påkrevd', 'error')
            return redirect(url_for('calendar.index'))

        # Valider dato format
        datetime.strptime(event_date, '%Y-%m-%d')

        # Valider tid hvis oppgitt
        if event_time:
            datetime.strptime(event_time, '%H:%M')

        result = execute_db(
            '''UPDATE calendar_events
               SET title = ?, description = ?, event_date = ?, event_time = ?,
                   location = ?, event_type = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (title, description, event_date, event_time or None, location or None, event_type, event_id)
        )

        if result:
            logger.info(f"Event updated by {user_name}: {title} (ID: {event_id})")
            flash(f'Hendelse "{title}" oppdatert!', 'success')
        else:
            flash('Feil ved oppdatering av hendelse', 'error')

    except ValueError as e:
        logger.error(f"Date validation error: {str(e)}")
        flash('Ugyldig dato eller klokkeslett format', 'error')
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        flash('Feil ved oppdatering av hendelse', 'error')

    return redirect(url_for('calendar.index'))

@bp.route('/delete/<int:event_id>', methods=['POST'])
@auth_required
def delete_event(event_id: int):
    """Slett hendelse"""
    user_name = get_user_display_name()

    try:
        # Hent hendelse info før sletting
        event = query_db(
            'SELECT title FROM calendar_events WHERE id = ?',
            (event_id,),
            one=True
        )

        if not event:
            flash('Hendelse ikke funnet', 'error')
            return redirect(url_for('calendar.index'))

        result = execute_db(
            'DELETE FROM calendar_events WHERE id = ?',
            (event_id,)
        )

        if result:
            logger.info(f"Event deleted by {user_name}: {event['title']} (ID: {event_id})")
            flash(f'Hendelse "{event["title"]}" slettet', 'success')
        else:
            flash('Feil ved sletting av hendelse', 'error')

    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        flash('Feil ved sletting av hendelse', 'error')

    return redirect(url_for('calendar.index'))

@bp.route('/api/events')
@auth_required
def api_events():
    """API endpoint for hendelser"""
    try:
        # Hent datoer fra query params
        start_date = request.args.get('start')
        end_date = request.args.get('end')

        if start_date and end_date:
            events = query_db(
                '''SELECT * FROM calendar_events
                   WHERE event_date >= ? AND event_date <= ?
                   ORDER BY event_date ASC, event_time ASC''',
                (start_date, end_date)
            )
        else:
            # Hent kommende 30 dager som standard
            today = datetime.now().date()
            end = today + timedelta(days=30)
            events = query_db(
                '''SELECT * FROM calendar_events
                   WHERE event_date >= ? AND event_date <= ?
                   ORDER BY event_date ASC, event_time ASC''',
                (today.isoformat(), end.isoformat())
            )

        return jsonify({
            'events': events,
            'count': len(events),
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch events',
            'status': 'error'
        }), 500

def get_event_type_icon(event_type: str) -> str:
    """Få ikon basert på hendelsestype"""
    icons = {
        'meeting': '👥',
        'deadline': '⚡',
        'birthday': '🎂',
        'holiday': '🏖️',
        'training': '📚',
        'presentation': '📊',
        'other': '📅'
    }
    return icons.get(event_type, '📅')

def get_event_type_color(event_type: str) -> str:
    """Få farge basert på hendelsestype"""
    colors = {
        'meeting': '#10B981',
        'deadline': '#DC2626',
        'birthday': '#F59E0B',
        'holiday': '#3B82F6',
        'training': '#8B5CF6',
        'presentation': '#06B6D4',
        'other': '#6B7280'
    }
    return colors.get(event_type, '#6B7280')

# Legg til hjelpefunksjoner i template context
@bp.app_template_global()
def event_icon(event_type):
    return get_event_type_icon(event_type)

@bp.app_template_global()
def event_color(event_type):
    return get_event_type_color(event_type)