import logging
from typing import List, Dict, Optional
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..utils.helpers import auth_required, get_current_user, get_user_display_name
from ..models.db import (
    get_suppliers, create_supplier, update_supplier,
    delete_supplier, get_supplier_by_id
)

bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')
logger = logging.getLogger(__name__)

@bp.route('/')
@auth_required
def index():
    """Leverandører hovedside"""
    user_name = get_user_display_name()
    logger.info(f"Suppliers accessed by {user_name}")

    try:
        # Hent alle leverandører sortert alfabetisk
        suppliers = get_suppliers()

        # Statistikk
        total_suppliers = len(suppliers)

        return render_template('suppliers/index.html',
                             suppliers=suppliers,
                             total_suppliers=total_suppliers,
                             user_name=user_name)

    except Exception as e:
        logger.error(f"Error loading suppliers: {str(e)}")
        flash('Feil ved lasting av leverandører', 'error')
        return render_template('suppliers/index.html',
                             suppliers=[],
                             total_suppliers=0,
                             user_name=user_name)

@bp.route('/create', methods=['POST'])
@auth_required
def create():
    """Opprett ny leverandør"""
    user_name = get_user_display_name()

    name = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    website = request.form.get('website', '').strip()

    if not name:
        flash('Navn er påkrevd', 'error')
        return redirect(url_for('suppliers.index'))

    # Valider website format hvis oppgitt
    if website and not website.startswith(('http://', 'https://')):
        website = 'https://' + website

    try:
        supplier_id = create_supplier(name, username, password, website, user_name)

        if supplier_id:
            logger.info(f"Supplier created by {user_name}: {name}")
            flash(f'Leverandør "{name}" opprettet!', 'success')
        else:
            flash('Feil ved opprettelse av leverandør', 'error')

    except Exception as e:
        logger.error(f"Error creating supplier: {str(e)}")
        flash('Feil ved opprettelse av leverandør', 'error')

    return redirect(url_for('suppliers.index'))

@bp.route('/edit/<int:supplier_id>', methods=['POST'])
@auth_required
def edit(supplier_id: int):
    """Rediger leverandør"""
    user_name = get_user_display_name()

    try:
        # Sjekk at leverandøren eksisterer
        supplier = get_supplier_by_id(supplier_id)
        if not supplier:
            flash('Leverandør ikke funnet', 'error')
            return redirect(url_for('suppliers.index'))

        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        website = request.form.get('website', '').strip()

        if not name:
            flash('Navn er påkrevd', 'error')
            return redirect(url_for('suppliers.index'))

        # Valider website format hvis oppgitt
        if website and not website.startswith(('http://', 'https://')):
            website = 'https://' + website

        success = update_supplier(supplier_id, name, username, password, website)

        if success:
            logger.info(f"Supplier updated by {user_name}: {name} (ID: {supplier_id})")
            flash(f'Leverandør "{name}" oppdatert!', 'success')
        else:
            flash('Feil ved oppdatering av leverandør', 'error')

    except Exception as e:
        logger.error(f"Error updating supplier: {str(e)}")
        flash('Feil ved oppdatering av leverandør', 'error')

    return redirect(url_for('suppliers.index'))

@bp.route('/delete/<int:supplier_id>', methods=['POST'])
@auth_required
def delete(supplier_id: int):
    """Slett leverandør"""
    user_name = get_user_display_name()

    try:
        # Hent leverandør info før sletting
        supplier = get_supplier_by_id(supplier_id)
        if not supplier:
            flash('Leverandør ikke funnet', 'error')
            return redirect(url_for('suppliers.index'))

        success = delete_supplier(supplier_id)

        if success:
            logger.info(f"Supplier deleted by {user_name}: {supplier['name']} (ID: {supplier_id})")
            flash(f'Leverandør "{supplier["name"]}" slettet', 'success')
        else:
            flash('Feil ved sletting av leverandør', 'error')

    except Exception as e:
        logger.error(f"Error deleting supplier: {str(e)}")
        flash('Feil ved sletting av leverandør', 'error')

    return redirect(url_for('suppliers.index'))

@bp.route('/api/suppliers')
@auth_required
def api_suppliers():
    """API endpoint for leverandører"""
    try:
        suppliers = get_suppliers()

        return jsonify({
            'suppliers': suppliers,
            'count': len(suppliers),
            'status': 'success'
        })

    except Exception as e:
        logger.error(f"Error fetching suppliers: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch suppliers',
            'status': 'error'
        }), 500