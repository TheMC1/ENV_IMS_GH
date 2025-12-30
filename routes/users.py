"""
User management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from routes.auth import admin_required
from database import (
    get_user_by_username,
    get_all_users,
    add_user as db_add_user,
    update_user as db_update_user,
    delete_user as db_delete_user,
    reset_user_password as db_reset_password,
    suspend_user as db_suspend_user,
    unsuspend_user as db_unsuspend_user
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
