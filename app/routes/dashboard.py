import logging
from typing import Dict, Any
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..utils.helpers import auth_required, get_current_user, get_user_display_name, get_user_email
from ..models.db import (
    get_posts, create_post, get_recent_events,
    get_task_summary, get_user_stats
)

bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

@bp.route('/')
@bp.route('/dashboard')
@auth_required
def index():
    """Dashboard hovedside med ekte data"""
    user = get_current_user()
    user_name = get_user_display_name()
    logger.info(f"Dashboard accessed by {user_name}")

    try:
        # Hent dashboard data
        posts = get_posts(limit=10)
        upcoming_events = get_recent_events(limit=5)
        task_summary = get_task_summary()
        stats = get_user_stats()

        # Dashboard context
        dashboard_data = {
            'user': user,
            'user_name': user_name,
            'posts': posts,
            'upcoming_events': upcoming_events,
            'task_summary': task_summary,
            'stats': stats
        }

        logger.debug(f"Dashboard data loaded: {len(posts)} posts, {len(upcoming_events)} events")
        return render_template('dashboard/index.html', **dashboard_data)

    except Exception as e:
        logger.error(f"Error loading dashboard data: {str(e)}")
        flash('Feil ved lasting av dashboard data', 'error')

        # Fallback - enkel dashboard
        return render_template('dashboard/index.html',
                             user=user,
                             user_name=user_name,
                             posts=[],
                             upcoming_events=[],
                             task_summary={'todo': 0, 'in_progress': 0, 'done': 0},
                             stats={'total_posts': 0, 'total_events': 0, 'total_tasks': 0, 'total_documents': 0})

@bp.route('/create_post', methods=['POST'])
@auth_required
def create_post_route():
    """Opprett nytt innlegg"""
    content = request.form.get('content', '').strip()

    if not content:
        flash('Innlegget kan ikke være tomt', 'error')
        return redirect(url_for('dashboard.index'))

    if len(content) > 1000:
        flash('Innlegget er for langt (max 1000 tegn)', 'error')
        return redirect(url_for('dashboard.index'))

    user_name = get_user_display_name()
    user_email = get_user_email()

    try:
        post_id = create_post(content, user_name, user_email)
        if post_id:
            logger.info(f"Post created by {user_name}: {content[:50]}...")
            flash('Innlegg opprettet!', 'success')
        else:
            flash('Feil ved opprettelse av innlegg', 'error')

    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        flash('Feil ved opprettelse av innlegg', 'error')

    return redirect(url_for('dashboard.index'))

@bp.route('/api/stats')
@auth_required
def api_stats():
    """API endpoint for dashboard statistikk"""
    try:
        stats = get_user_stats()
        task_summary = get_task_summary()

        return jsonify({
            'stats': stats,
            'tasks': task_summary,
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch statistics',
            'status': 'error'
        }), 500

@bp.route('/api/posts')
@auth_required
def api_posts():
    """API endpoint for posts"""
    try:
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(limit, 1), 50)  # Begrenset til 1-50

        posts = get_posts(limit=limit)

        return jsonify({
            'posts': posts,
            'count': len(posts),
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching posts: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch posts',
            'status': 'error'
        }), 500