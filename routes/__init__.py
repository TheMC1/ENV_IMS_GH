"""
Routes package for Carbon IMS
Contains Flask blueprints for modular routing.
"""

from routes.auth import auth_bp, login_required, admin_required, write_access_required, page_access_required
from routes.users import users_bp
from routes.inventory import inventory_bp
from routes.backups import backups_bp
from routes.warranties import warranties_bp
from routes.dashboard import dashboard_bp
from routes.settings import settings_bp
from routes.registry import registry_bp
from routes.trades import trades_bp
from routes.reports import reports_bp

__all__ = [
    'auth_bp',
    'users_bp',
    'inventory_bp',
    'backups_bp',
    'warranties_bp',
    'dashboard_bp',
    'settings_bp',
    'registry_bp',
    'trades_bp',
    'reports_bp',
    'login_required',
    'admin_required',
    'write_access_required',
    'page_access_required'
]
