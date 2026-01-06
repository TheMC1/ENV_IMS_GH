"""
User management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from routes.auth import admin_required
from database import (
    get_user_by_username,
    get_all_users,
    add_user as db_add_user,
    update_user as db_update_user,
    delete_user as db_delete_user,
    reset_user_password as db_reset_password,
    suspend_user as db_suspend_user,
    unsuspend_user as db_unsuspend_user,
    get_all_role_permissions,
    get_role_permissions,
    update_role_permissions,
    get_available_pages,
    get_available_roles,
    is_logging_enabled,
    set_logging_enabled,
    is_backup_tracking_enabled,
    set_backup_tracking_enabled
)

users_bp = Blueprint('users', __name__)


@users_bp.route('/users')
@admin_required
def manage_users():
    """Display user management page"""
    username = session.get('user')
    users_from_db = get_all_users()
    user_list = []
    for user in users_from_db:
        user_list.append({
            'username': user['username'],
            'first_name': user['first_name'] or '',
            'last_name': user['last_name'] or '',
            'email': user['email'] or '',
            'display_name': user['display_name'] or '',
            'role': user['role'],
            'is_suspended': user['is_suspended']
        })
    return render_template('users.html', username=username, users=user_list)


@users_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    """Create a new user"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    display_name = request.form.get('display_name', '').strip()
    role = request.form.get('role', 'user')

    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_add_user(username, password, first_name, last_name, email, display_name, role)
    if success:
        flash(f'User "{username}" has been created successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


@users_bp.route('/users/edit', methods=['POST'])
@admin_required
def edit_user():
    """Update an existing user"""
    old_username = request.form.get('old_username', '').strip()
    new_username = request.form.get('username', '').strip()
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    display_name = request.form.get('display_name', '').strip()
    role = request.form.get('role', 'user')

    if not old_username or not new_username:
        flash('Username is required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_update_user(old_username, new_username, first_name, last_name, email, display_name, role)
    if success:
        flash(f'User "{new_username}" has been updated successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


@users_bp.route('/users/delete', methods=['POST'])
@admin_required
def delete_user():
    """Delete a user"""
    username = request.form.get('username', '').strip()
    current_user = session.get('user')

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_delete_user(username, current_user)
    if success:
        flash(f'User "{username}" has been deleted successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


@users_bp.route('/users/reset-password', methods=['POST'])
@admin_required
def reset_password():
    """Reset a user's password"""
    username = request.form.get('username', '').strip()
    new_password = request.form.get('new_password', '')

    if not username or not new_password:
        flash('Username and new password are required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_reset_password(username, new_password)
    if success:
        flash(f'Password for "{username}" has been reset successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


@users_bp.route('/users/suspend', methods=['POST'])
@admin_required
def suspend_user():
    """Suspend a user account"""
    username = request.form.get('username', '').strip()
    current_user = session.get('user')

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_suspend_user(username, current_user)
    if success:
        flash(f'User "{username}" has been suspended.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


@users_bp.route('/users/unsuspend', methods=['POST'])
@admin_required
def unsuspend_user():
    """Unsuspend a user account"""
    username = request.form.get('username', '').strip()

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('users.manage_users'))

    success, message = db_unsuspend_user(username)
    if success:
        flash(f'User "{username}" has been unsuspended.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('users.manage_users'))


# Role Permissions API Endpoints
@users_bp.route('/api/roles/permissions', methods=['GET'])
@admin_required
def get_permissions():
    """Get all role permissions"""
    try:
        permissions = get_all_role_permissions()
        pages = get_available_pages()
        roles = get_available_roles()

        return jsonify({
            'permissions': permissions,
            'pages': pages,
            'roles': roles
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/roles/permissions/<role>', methods=['GET'])
@admin_required
def get_role_perms(role):
    """Get permissions for a specific role"""
    try:
        permissions = get_role_permissions(role)
        return jsonify({'role': role, 'allowed_pages': permissions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/roles/permissions/<role>', methods=['POST'])
@admin_required
def update_role_perms(role):
    """Update permissions for a role"""
    try:
        data = request.json
        allowed_pages = data.get('allowed_pages', [])

        # Admin role must always have access to users and settings
        if role == 'admin':
            if 'users' not in allowed_pages:
                allowed_pages.append('users')
            if 'settings' not in allowed_pages:
                allowed_pages.append('settings')

        success, message = update_role_permissions(role, allowed_pages)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# System Settings API Endpoints
@users_bp.route('/api/system/logging-status', methods=['GET'])
@admin_required
def get_logging_status():
    """Get the current activity logging status"""
    try:
        enabled = is_logging_enabled()
        return jsonify({
            'success': True,
            'logging_enabled': enabled
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/system/logging-status', methods=['POST'])
@admin_required
def set_logging_status():
    """Enable or disable activity logging"""
    try:
        data = request.json
        enabled = data.get('enabled', True)
        username = session.get('user')

        success, message = set_logging_enabled(enabled, username)

        if success:
            status = 'enabled' if enabled else 'paused'
            return jsonify({
                'success': True,
                'message': f'Activity logging {status}',
                'logging_enabled': enabled
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/system/backup-tracking-status', methods=['GET'])
@admin_required
def get_backup_tracking_status():
    """Get the current backup tracking status"""
    try:
        enabled = is_backup_tracking_enabled()
        return jsonify({
            'success': True,
            'backup_tracking_enabled': enabled
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/system/backup-tracking-status', methods=['POST'])
@admin_required
def set_backup_tracking_status():
    """Enable or disable backup tracking"""
    try:
        data = request.json
        enabled = data.get('enabled', True)
        username = session.get('user')

        success, message = set_backup_tracking_enabled(enabled, username)

        if success:
            status = 'enabled' if enabled else 'paused'
            return jsonify({
                'success': True,
                'message': f'Backup tracking {status}',
                'backup_tracking_enabled': enabled
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
