"""
Authentication routes and decorators for Carbon IMS
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from database import get_user_by_username, verify_user_password

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """Decorator to require user authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        user = get_user_by_username(session['user'])
        if not user or user['role'] != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.home'))
        return f(*args, **kwargs)
    return decorated_function


def write_access_required(f):
    """Decorator to ensure user has write access (admin or trader roles only)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = get_user_by_username(session['user'])
        if not user:
            return jsonify({'error': 'User not found'}), 401
        # Only admin and trader have write access, ops is read-only
        if user['role'] not in ['admin', 'trader']:
            return jsonify({'error': 'You do not have permission to modify the inventory. Your role is read-only.'}), 403
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/')
def index():
    """Redirect to home or login based on session state"""
    if 'user' in session:
        return redirect(url_for('auth.home'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if 'user' in session:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')

        success, message = verify_user_password(username, password)
        if success:
            session['user'] = username
            session.permanent = False
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('auth.home'))
        else:
            flash(message, 'danger')
            return render_template('login.html')

    return render_template('login.html')


@auth_bp.route('/home')
@login_required
def home():
    """User home/dashboard page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'
    display_name = user['display_name'] if user and user['display_name'] else username
    return render_template('home.html', username=username, display_name=display_name, user_role=user_role)


@auth_bp.route('/logout')
def logout():
    """Handle user logout"""
    session.pop('user', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/auth/validate-password', methods=['POST'])
@login_required
def validate_password():
    """Validate user password for sensitive operations"""
    try:
        username = session.get('user')
        password = request.json.get('password')

        if not password:
            return jsonify({'valid': False, 'error': 'Password is required'}), 400

        success, message = verify_user_password(username, password)

        if success:
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False, 'error': message}), 401
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500


@auth_bp.route('/api/verify-password', methods=['POST'])
@login_required
def verify_password_endpoint():
    """Verify user password for delete operations"""
    try:
        username = session.get('user')
        password = request.json.get('password')

        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        success, message = verify_user_password(username, password)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': message}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
