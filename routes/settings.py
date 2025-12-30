"""
Settings and user preferences routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from routes.auth import login_required
from database import (
    get_user_by_username,
    verify_user_password,
    update_user_settings,
    update_user_preferences,
    get_user_page_settings,
    save_user_page_settings
)

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings and preferences page"""
    username = session.get('user')
    user = get_user_by_username(username)

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        view_mode = request.form.get('view_mode', '')
        custody_view = request.form.get('custody_view', '')
        rows_per_page = request.form.get('rows_per_page', '')
        warranty_view_mode = request.form.get('warranty_view_mode', '')
        warranty_custody_view = request.form.get('warranty_custody_view', '')
        warranty_rows_per_page = request.form.get('warranty_rows_per_page', '')

        # Verify current password if trying to change password
        if new_password or confirm_password:
            if not current_password:
                flash('Please enter your current password to change your password.', 'danger')
                return render_template('settings.html', user=user)

            success, message = verify_user_password(username, current_password)
            if not success:
                flash('Current password is incorrect.', 'danger')
                return render_template('settings.html', user=user)

            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return render_template('settings.html', user=user)

            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return render_template('settings.html', user=user)

        # Update settings
        update_display_name = display_name if display_name else None
        update_password = new_password if new_password else None
        update_view_mode = view_mode if view_mode else None
        update_custody_view = custody_view if custody_view else None
        update_rows_per_page = rows_per_page if rows_per_page else None
        update_warranty_view_mode = warranty_view_mode if warranty_view_mode else None
        update_warranty_custody_view = warranty_custody_view if warranty_custody_view else None
        update_warranty_rows_per_page = warranty_rows_per_page if warranty_rows_per_page else None

        # Check if there are any changes
        has_changes = (update_display_name is not None or
                      update_password is not None or
                      update_view_mode is not None or
                      update_custody_view is not None or
                      update_rows_per_page is not None or
                      update_warranty_view_mode is not None or
                      update_warranty_custody_view is not None or
                      update_warranty_rows_per_page is not None)

        if not has_changes:
            flash('No changes to save.', 'warning')
            return render_template('settings.html', user=user)

        # Update user settings (display name and password)
        if update_display_name is not None or update_password is not None:
            success, message = update_user_settings(username, update_display_name, update_password)
            if not success:
                flash(f'Error: {message}', 'danger')
                return render_template('settings.html', user=user)

        # Update user preferences
        if (update_view_mode is not None or update_custody_view is not None or
            update_rows_per_page is not None or update_warranty_view_mode is not None or
            update_warranty_custody_view is not None or update_warranty_rows_per_page is not None):
            success, message = update_user_preferences(username, update_view_mode, update_custody_view,
                                                      update_rows_per_page, update_warranty_view_mode,
                                                      update_warranty_custody_view, update_warranty_rows_per_page)
            if not success:
                flash(f'Error: {message}', 'danger')
                return render_template('settings.html', user=user)

        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings.settings'))

    return render_template('settings.html', user=user)


@settings_bp.route('/api/settings/<page>', methods=['GET'])
@login_required
def get_page_settings(page):
    """Get user settings for a specific page"""
    try:
        username = session.get('user')
        page_settings = get_user_page_settings(username, page)
        return jsonify({'success': True, 'settings': page_settings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/settings/<page>', methods=['POST'])
@login_required
def save_page_settings_route(page):
    """Save user settings for a specific page"""
    try:
        username = session.get('user')
        page_settings = request.json

        if page_settings is None:
            return jsonify({'error': 'No settings provided'}), 400

        success, message = save_user_page_settings(username, page, page_settings)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
