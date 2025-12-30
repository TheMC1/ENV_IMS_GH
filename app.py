"""
Carbon IMS - Inventory Management System
Main application entry point with Flask blueprints
"""

from flask import Flask
import secrets
import os

from database import init_database, init_inventory_database, get_all_inventory_items, migrate_csv_to_database

# Import blueprints
from routes import (
    auth_bp,
    users_bp,
    inventory_bp,
    backups_bp,
    warranties_bp,
    dashboard_bp,
    settings_bp,
    registry_bp,
    trades_bp
)

# Create Flask application
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Initialize databases
init_database()
init_inventory_database()

# Migrate CSV data to database if CSV exists and database is empty
CSV_FILE = 'inventory.csv'
if os.path.exists(CSV_FILE):
    items = get_all_inventory_items()
    if len(items) == 0:
        print("Migrating CSV data to database...")
        success, message = migrate_csv_to_database(CSV_FILE)
        if success:
            print("CSV migration completed successfully!")
            os.rename(CSV_FILE, CSV_FILE + '.migrated')
        else:
            print(f"CSV migration failed: {message}")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(backups_bp)
app.register_blueprint(warranties_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(registry_bp)
app.register_blueprint(trades_bp)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
