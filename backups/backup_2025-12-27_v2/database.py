import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime

DATABASE_PATH = 'ims_users.db'
INVENTORY_DB_PATH = 'ims_inventory.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_inventory_db_connection():
    conn = sqlite3.connect(INVENTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            display_name TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            is_suspended INTEGER NOT NULL DEFAULT 0,
            view_mode TEXT DEFAULT 'summarized',
            custody_view TEXT DEFAULT 'all',
            rows_per_page TEXT DEFAULT 'all',
            warranty_view_mode TEXT DEFAULT 'summarized',
            warranty_custody_view TEXT DEFAULT 'all',
            warranty_rows_per_page TEXT DEFAULT 'all',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Check if new columns exist, add them if not (for existing databases)
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'first_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    if 'last_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
    if 'email' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if 'display_name' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    if 'is_suspended' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_suspended INTEGER NOT NULL DEFAULT 0")
    if 'view_mode' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN view_mode TEXT DEFAULT 'summarized'")
    if 'custody_view' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN custody_view TEXT DEFAULT 'all'")
    if 'rows_per_page' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN rows_per_page TEXT DEFAULT 'all'")
    if 'warranty_view_mode' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN warranty_view_mode TEXT DEFAULT 'summarized'")
    if 'warranty_custody_view' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN warranty_custody_view TEXT DEFAULT 'all'")
    if 'warranty_rows_per_page' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN warranty_rows_per_page TEXT DEFAULT 'all'")

    # Create user_settings table for storing dashboard and page settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            page TEXT NOT NULL,
            settings TEXT NOT NULL DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, page)
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password, first_name, last_name, email, display_name, role, is_suspended) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 'System', 'Administrator', 'admin@ims.local', 'Admin', 'admin', 0)
        )
        print("Default admin user created successfully.")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def verify_user_password(username, password):
    user = get_user_by_username(username)
    if user and check_password_hash(user['password'], password):
        if user['is_suspended'] == 1:
            return False, "Account is suspended"
        return True, "Login successful"
    return False, "Invalid credentials"

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, first_name, last_name, email, display_name, role, is_suspended, created_at FROM users ORDER BY username")
    users = cursor.fetchall()
    conn.close()
    return users

def add_user(username, password, first_name='', last_name='', email='', display_name='', role='user'):
    if get_user_by_username(username):
        return False, "User already exists"

    if role not in ['admin', 'user', 'trader', 'ops']:
        role = 'user'

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, first_name, last_name, email, display_name, role, is_suspended) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), first_name, last_name, email, display_name, role, 0)
        )
        conn.commit()
        conn.close()
        return True, "User created successfully"
    except sqlite3.IntegrityError:
        return False, "User already exists"
    except Exception as e:
        return False, str(e)

def update_user(old_username, new_username, first_name, last_name, email, display_name, role):
    if old_username == 'admin':
        return False, "Cannot modify the admin user"

    if role not in ['admin', 'user', 'trader', 'ops']:
        role = 'user'

    if old_username != new_username and get_user_by_username(new_username):
        return False, "New username already exists"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET username = ?, first_name = ?, last_name = ?, email = ?, display_name = ?, role = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
            (new_username, first_name, last_name, email, display_name, role, old_username)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "User updated successfully"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    except Exception as e:
        return False, str(e)

def delete_user(username, current_user):
    if username == 'admin':
        return False, "Cannot delete the admin user"

    if username == current_user:
        return False, "Cannot delete your own account"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "User deleted successfully"
    except Exception as e:
        return False, str(e)

def reset_user_password(username, new_password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
            (generate_password_hash(new_password), username)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "Password reset successfully"
    except Exception as e:
        return False, str(e)

def suspend_user(username, current_user):
    if username == 'admin':
        return False, "Cannot suspend the admin user"

    if username == current_user:
        return False, "Cannot suspend your own account"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_suspended = 1, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
            (username,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "User suspended successfully"
    except Exception as e:
        return False, str(e)

def unsuspend_user(username):
    if username == 'admin':
        return False, "Cannot modify the admin user"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_suspended = 0, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
            (username,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "User unsuspended successfully"
    except Exception as e:
        return False, str(e)

def update_user_settings(username, display_name=None, new_password=None):
    """Update user's display name and/or password"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if display_name is not None and new_password is not None:
            cursor.execute(
                "UPDATE users SET display_name = ?, password = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                (display_name, generate_password_hash(new_password), username)
            )
        elif display_name is not None:
            cursor.execute(
                "UPDATE users SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                (display_name, username)
            )
        elif new_password is not None:
            cursor.execute(
                "UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                (generate_password_hash(new_password), username)
            )
        else:
            return False, "No changes to make"

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "Settings updated successfully"
    except Exception as e:
        return False, str(e)

def update_user_preferences(username, view_mode=None, custody_view=None, rows_per_page=None,
                           warranty_view_mode=None, warranty_custody_view=None, warranty_rows_per_page=None):
    """Update user's inventory and warranty view preferences"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if view_mode is not None:
            updates.append("view_mode = ?")
            params.append(view_mode)
        if custody_view is not None:
            updates.append("custody_view = ?")
            params.append(custody_view)
        if rows_per_page is not None:
            updates.append("rows_per_page = ?")
            params.append(rows_per_page)
        if warranty_view_mode is not None:
            updates.append("warranty_view_mode = ?")
            params.append(warranty_view_mode)
        if warranty_custody_view is not None:
            updates.append("warranty_custody_view = ?")
            params.append(warranty_custody_view)
        if warranty_rows_per_page is not None:
            updates.append("warranty_rows_per_page = ?")
            params.append(warranty_rows_per_page)

        if not updates:
            return False, "No changes to make"

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(username)

        query = f"UPDATE users SET {', '.join(updates)} WHERE username = ?"
        cursor.execute(query, params)

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "User not found"
        return True, "Preferences updated successfully"
    except Exception as e:
        return False, str(e)

def init_inventory_database():
    """Initialize inventory database with individual columns for each field"""
    conn = get_inventory_db_connection()
    cursor = conn.cursor()

    # Create inventory table with individual columns for each metadata field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market TEXT,
            registry TEXT,
            product TEXT,
            project_id TEXT,
            project_type TEXT,
            protocol TEXT,
            project_name TEXT,
            serial TEXT UNIQUE,
            is_custody TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create backups table to store inventory snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            summary TEXT,
            backup_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create warranties table (minimal structure - other data from inventory)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warranties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT UNIQUE NOT NULL,
            buy_start TEXT,
            buy_end TEXT,
            sell_start TEXT,
            sell_end TEXT,
            buy_tradeid INTEGER,
            sell_tradeid INTEGER,
            buy_client TEXT,
            sell_client TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: Check if old column names exist and rename/add new columns
    cursor.execute("PRAGMA table_info(warranties)")
    warranty_columns = [column[1] for column in cursor.fetchall()]

    # Migrate from old column names to new ones
    # warranty_start/warranty_end -> warranty_buy_start/warranty_buy_end -> buy_start/buy_end
    if 'warranty_start' in warranty_columns and 'buy_start' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_start TO buy_start")
    if 'warranty_end' in warranty_columns and 'buy_end' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_end TO buy_end")
    if 'warranty_buy_start' in warranty_columns and 'buy_start' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_buy_start TO buy_start")
    if 'warranty_buy_end' in warranty_columns and 'buy_end' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_buy_end TO buy_end")
    if 'warranty_sell_start' in warranty_columns and 'sell_start' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_sell_start TO sell_start")
    if 'warranty_sell_end' in warranty_columns and 'sell_end' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN warranty_sell_end TO sell_end")

    # Rename opl_tradeid to buy_tradeid and client to buy_client
    if 'opl_tradeid' in warranty_columns and 'buy_tradeid' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN opl_tradeid TO buy_tradeid")
    if 'client' in warranty_columns and 'buy_client' not in warranty_columns:
        cursor.execute("ALTER TABLE warranties RENAME COLUMN client TO buy_client")

    # Add new columns if they don't exist
    # Re-fetch columns after renames
    cursor.execute("PRAGMA table_info(warranties)")
    warranty_columns = [column[1] for column in cursor.fetchall()]

    if 'sell_start' not in warranty_columns:
        try:
            cursor.execute("ALTER TABLE warranties ADD COLUMN sell_start TEXT")
        except:
            pass
    if 'sell_end' not in warranty_columns:
        try:
            cursor.execute("ALTER TABLE warranties ADD COLUMN sell_end TEXT")
        except:
            pass
    if 'sell_tradeid' not in warranty_columns:
        try:
            cursor.execute("ALTER TABLE warranties ADD COLUMN sell_tradeid INTEGER")
        except:
            pass
    if 'sell_client' not in warranty_columns:
        try:
            cursor.execute("ALTER TABLE warranties ADD COLUMN sell_client TEXT")
        except:
            pass

    conn.commit()
    conn.close()
    print("Inventory database initialized successfully.")

def get_all_inventory_items():
    """Get all inventory items from individual columns"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, project_name, serial, is_custody
            FROM inventory
            ORDER BY id
        """)
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            item_data = {
                '_row_index': row['id'],
                'Market': row['market'] or '',
                'Registry': row['registry'] or '',
                'Product': row['product'] or '',
                'ProjectID': row['project_id'] or '',
                'ProjectType': row['project_type'] or '',
                'Protocol': row['protocol'] or '',
                'ProjectName': row['project_name'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or ''
            }
            items.append(item_data)

        return items
    except Exception as e:
        print(f"Error getting inventory items: {e}")
        return []

def get_inventory_headers():
    """Get all unique headers from inventory items in specified order"""
    items = get_all_inventory_items()
    if not items:
        return []

    # Collect all unique keys across all items
    headers_set = set()
    for item in items:
        for key in item.keys():
            if key != '_row_index':
                headers_set.add(key)

    # Define preferred column order
    preferred_order = [
        'Market',
        'Registry',
        'Product',
        'ProjectID',
        'ProjectType',
        'Protocol',
        'ProjectName',
        'Serial',
        'IsCustody'
    ]

    # Order headers according to preferred order
    ordered_headers = []

    # First, add headers that are in the preferred order
    for header in preferred_order:
        if header in headers_set:
            ordered_headers.append(header)

    # Then, add any additional headers that aren't in the preferred order (sorted)
    remaining_headers = sorted([h for h in headers_set if h not in preferred_order])
    ordered_headers.extend(remaining_headers)

    return ordered_headers

def add_inventory_item(item_data):
    """Add a new inventory item and automatically create corresponding warranty"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Remove _row_index if present
        clean_data = {k: v for k, v in item_data.items() if k != '_row_index'}

        # Get Serial for warranty creation
        serial = clean_data.get('Serial', '')

        # Insert into individual columns
        cursor.execute("""
            INSERT INTO inventory (market, registry, product, project_id, project_type,
                                 protocol, project_name, serial, is_custody)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clean_data.get('Market', ''),
            clean_data.get('Registry', ''),
            clean_data.get('Product', ''),
            clean_data.get('ProjectID', ''),
            clean_data.get('ProjectType', ''),
            clean_data.get('Protocol', ''),
            clean_data.get('ProjectName', ''),
            clean_data.get('Serial', ''),
            clean_data.get('IsCustody', '')
        ))

        item_id = cursor.lastrowid

        # Automatically create warranty record for one-to-one relationship
        if serial:
            try:
                cursor.execute(
                    "INSERT INTO warranties (serial, buy_start, buy_end, sell_start, sell_end, buy_tradeid, sell_tradeid, buy_client, sell_client) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (serial, '', '', '', '', None, None, '', '')
                )
            except Exception as warranty_error:
                # If warranty creation fails, rollback inventory insert
                conn.rollback()
                conn.close()
                return False, f"Failed to create warranty: {warranty_error}"

        conn.commit()
        conn.close()

        return True, item_id
    except Exception as e:
        return False, str(e)

def update_inventory_item(item_id, item_data):
    """Update an inventory item and CASCADE serial changes to warranties"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Remove _row_index if present
        clean_data = {k: v for k, v in item_data.items() if k != '_row_index'}

        # Get the old serial before updating
        cursor.execute("SELECT serial FROM inventory WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Item not found"

        old_serial = row['serial'] or ''
        new_serial = clean_data.get('Serial', '')

        # Update individual columns
        cursor.execute("""
            UPDATE inventory
            SET market = ?, registry = ?, product = ?, project_id = ?, project_type = ?,
                protocol = ?, project_name = ?, serial = ?, is_custody = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            clean_data.get('Market', ''),
            clean_data.get('Registry', ''),
            clean_data.get('Product', ''),
            clean_data.get('ProjectID', ''),
            clean_data.get('ProjectType', ''),
            clean_data.get('Protocol', ''),
            clean_data.get('ProjectName', ''),
            new_serial,
            clean_data.get('IsCustody', ''),
            item_id
        ))

        # If serial changed, update the corresponding warranty's serial (CASCADE)
        if old_serial != new_serial and old_serial:
            cursor.execute(
                "UPDATE warranties SET serial = ? WHERE serial = ?",
                (new_serial, old_serial)
            )

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "Item not found"
        return True, "Item updated successfully"
    except Exception as e:
        return False, str(e)

def delete_inventory_item(item_id):
    """Delete an inventory item and its corresponding warranty"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get Serial before deleting inventory
        cursor.execute("SELECT serial FROM inventory WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Item not found"

        serial = row['serial'] or ''

        # Delete inventory item
        cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        affected = cursor.rowcount

        # Delete corresponding warranty to maintain one-to-one relationship
        if serial:
            cursor.execute("DELETE FROM warranties WHERE serial = ?", (serial,))

        conn.commit()
        conn.close()

        if affected == 0:
            return False, "Item not found"
        return True, "Item deleted successfully"
    except Exception as e:
        return False, str(e)

def create_inventory_backup(username, action, summary=None):
    """Create a backup snapshot of the entire inventory"""
    try:
        # Get all current inventory data
        items = get_all_inventory_items()

        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO inventory_backups (username, action, summary, backup_data) VALUES (?, ?, ?, ?)",
            (username, action, json.dumps(summary) if summary else None, json.dumps(items))
        )

        conn.commit()
        backup_id = cursor.lastrowid
        conn.close()

        return True, backup_id
    except Exception as e:
        return False, str(e)

def get_all_inventory_backups():
    """Get all inventory backups with metadata"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, action, summary, created_at
            FROM inventory_backups
            ORDER BY created_at DESC
        """)
        backups = cursor.fetchall()
        conn.close()

        result = []
        for backup in backups:
            backup_dict = dict(backup)
            if backup_dict['summary']:
                backup_dict['summary'] = json.loads(backup_dict['summary'])
            result.append(backup_dict)

        return result
    except Exception as e:
        print(f"Error getting backups: {e}")
        return []

def restore_inventory_backup(backup_id):
    """Restore inventory from a backup snapshot"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get the backup data
        cursor.execute("SELECT backup_data FROM inventory_backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Backup not found"

        backup_items = json.loads(row['backup_data'])

        # Clear current inventory
        cursor.execute("DELETE FROM inventory")

        # Restore items from backup
        for item in backup_items:
            clean_data = {k: v for k, v in item.items() if k != '_row_index'}
            cursor.execute("""
                INSERT INTO inventory (market, registry, product, project_id, project_type,
                                     protocol, project_name, serial, is_custody)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clean_data.get('Market', ''),
                clean_data.get('Registry', ''),
                clean_data.get('Product', ''),
                clean_data.get('ProjectID', ''),
                clean_data.get('ProjectType', ''),
                clean_data.get('Protocol', ''),
                clean_data.get('ProjectName', ''),
                clean_data.get('Serial', ''),
                clean_data.get('IsCustody', '')
            ))

        conn.commit()
        conn.close()

        return True, "Backup restored successfully"
    except Exception as e:
        return False, str(e)

def delete_inventory_backup(backup_id):
    """Delete a specific backup"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM inventory_backups WHERE id = ?", (backup_id,))

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "Backup not found"
        return True, "Backup deleted successfully"
    except Exception as e:
        return False, str(e)

def migrate_csv_to_database(csv_file_path):
    """Migrate existing CSV data to database"""
    import csv

    try:
        if not os.path.exists(csv_file_path):
            return False, "CSV file not found"

        with open(csv_file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                add_inventory_item(row)

        return True, "CSV data migrated successfully"
    except Exception as e:
        return False, str(e)

# Warranty Management Functions

def get_all_warranty_items():
    """Get all warranty items by joining with inventory on Serial"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Join warranties with inventory on Serial
        cursor.execute("""
            SELECT
                w.id,
                w.serial,
                w.buy_start,
                w.buy_end,
                w.sell_start,
                w.sell_end,
                w.buy_tradeid,
                w.sell_tradeid,
                w.buy_client,
                w.sell_client,
                i.market,
                i.registry,
                i.product,
                i.project_id,
                i.project_type,
                i.protocol,
                i.project_name,
                i.is_custody
            FROM warranties w
            LEFT JOIN inventory i ON i.serial = w.serial
            ORDER BY w.id
        """)
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            # Combine warranty and inventory data
            item_data = {
                '_row_index': row['id'],
                'Serial': row['serial'],
                'Buy_Start': row['buy_start'] or '',
                'Buy_End': row['buy_end'] or '',
                'Sell_Start': row['sell_start'] or '',
                'Sell_End': row['sell_end'] or '',
                'Buy_TradeID': row['buy_tradeid'] if row['buy_tradeid'] is not None else '',
                'Sell_TradeID': row['sell_tradeid'] if row['sell_tradeid'] is not None else '',
                'Buy_Client': row['buy_client'] or '',
                'Sell_Client': row['sell_client'] or '',
                'Market': row['market'] or '',
                'Registry': row['registry'] or '',
                'Product': row['product'] or '',
                'ProjectID': row['project_id'] or '',
                'ProjectType': row['project_type'] or '',
                'Protocol': row['protocol'] or '',
                'ProjectName': row['project_name'] or '',
                'IsCustody': row['is_custody'] or ''
            }

            items.append(item_data)

        return items
    except Exception as e:
        print(f"Error getting warranty items: {e}")
        return []

def get_warranty_headers():
    """Get all unique headers from warranty items in specified order"""
    items = get_all_warranty_items()
    if not items:
        return []

    # Collect all unique keys across all items
    headers_set = set()
    for item in items:
        for key in item.keys():
            if key != '_row_index':
                headers_set.add(key)

    # Define preferred column order for warranties
    preferred_order = [
        'Market',
        'Registry',
        'Product',
        'ProjectID',
        'ProjectType',
        'Protocol',
        'ProjectName',
        'IsCustody',
        'Serial',
        'Buy_Start',
        'Buy_End',
        'Buy_TradeID',
        'Buy_Client',
        'Sell_Start',
        'Sell_End',
        'Sell_TradeID',
        'Sell_Client'
    ]

    # Order headers according to preferred order
    ordered_headers = []

    # First, add headers that are in the preferred order
    for header in preferred_order:
        if header in headers_set:
            ordered_headers.append(header)

    # Then, add any additional headers that aren't in the preferred order (sorted)
    remaining_headers = sorted([h for h in headers_set if h not in preferred_order])
    ordered_headers.extend(remaining_headers)

    return ordered_headers

def add_warranty_item(item_data):
    """Add a new warranty item (only warranty fields: Serial, Buy_Start, Buy_End, Sell_Start, Sell_End, Buy_TradeID, Sell_TradeID, Buy_Client, Sell_Client)
    Validates that Serial exists in inventory to maintain one-to-one relationship"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        serial = item_data.get('Serial', '')
        buy_start = item_data.get('Buy_Start', '')
        buy_end = item_data.get('Buy_End', '')
        sell_start = item_data.get('Sell_Start', '')
        sell_end = item_data.get('Sell_End', '')
        buy_tradeid = item_data.get('Buy_TradeID', None)
        sell_tradeid = item_data.get('Sell_TradeID', None)
        buy_client = item_data.get('Buy_Client', '')
        sell_client = item_data.get('Sell_Client', '')

        # Convert TradeIDs to int if they're non-empty strings
        if buy_tradeid == '' or buy_tradeid is None:
            buy_tradeid = None
        else:
            try:
                buy_tradeid = int(buy_tradeid)
            except (ValueError, TypeError):
                buy_tradeid = None

        if sell_tradeid == '' or sell_tradeid is None:
            sell_tradeid = None
        else:
            try:
                sell_tradeid = int(sell_tradeid)
            except (ValueError, TypeError):
                sell_tradeid = None

        if not serial:
            conn.close()
            return False, "Serial is required"

        # Validate that Serial exists in inventory (one-to-one relationship)
        cursor.execute(
            "SELECT COUNT(*) FROM inventory WHERE serial = ?",
            (serial,)
        )
        count = cursor.fetchone()[0]

        if count == 0:
            conn.close()
            return False, f"Serial '{serial}' does not exist in inventory. Add inventory item first."

        cursor.execute(
            "INSERT INTO warranties (serial, buy_start, buy_end, sell_start, sell_end, buy_tradeid, sell_tradeid, buy_client, sell_client) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (serial, buy_start, buy_end, sell_start, sell_end, buy_tradeid, sell_tradeid, buy_client, sell_client)
        )

        conn.commit()
        item_id = cursor.lastrowid
        conn.close()

        return True, item_id
    except Exception as e:
        return False, str(e)

def update_warranty_item(item_id, item_data):
    """Update a warranty item (only warranty fields can be updated: Buy_Start, Buy_End, Sell_Start, Sell_End, Buy_TradeID, Sell_TradeID, Buy_Client, Sell_Client)"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Only update warranty fields, not Serial
        buy_start = item_data.get('Buy_Start', '')
        buy_end = item_data.get('Buy_End', '')
        sell_start = item_data.get('Sell_Start', '')
        sell_end = item_data.get('Sell_End', '')
        buy_tradeid = item_data.get('Buy_TradeID', None)
        sell_tradeid = item_data.get('Sell_TradeID', None)
        buy_client = item_data.get('Buy_Client', '')
        sell_client = item_data.get('Sell_Client', '')

        # Convert TradeIDs to int if they're non-empty strings
        if buy_tradeid == '' or buy_tradeid is None:
            buy_tradeid = None
        else:
            try:
                buy_tradeid = int(buy_tradeid)
            except (ValueError, TypeError):
                buy_tradeid = None

        if sell_tradeid == '' or sell_tradeid is None:
            sell_tradeid = None
        else:
            try:
                sell_tradeid = int(sell_tradeid)
            except (ValueError, TypeError):
                sell_tradeid = None

        cursor.execute(
            "UPDATE warranties SET buy_start = ?, buy_end = ?, sell_start = ?, sell_end = ?, buy_tradeid = ?, sell_tradeid = ?, buy_client = ?, sell_client = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (buy_start, buy_end, sell_start, sell_end, buy_tradeid, sell_tradeid, buy_client, sell_client, item_id)
        )

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        if affected == 0:
            return False, "Item not found"
        return True, "Item updated successfully"
    except Exception as e:
        return False, str(e)

def delete_warranty_item(item_id):
    """Delete a warranty item and its corresponding inventory item to maintain one-to-one relationship"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get Serial before deleting warranty
        cursor.execute("SELECT serial FROM warranties WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Item not found"

        serial = row['serial']

        # Delete warranty
        cursor.execute("DELETE FROM warranties WHERE id = ?", (item_id,))
        affected = cursor.rowcount

        # Delete corresponding inventory item to maintain one-to-one relationship
        if serial:
            cursor.execute(
                "DELETE FROM inventory WHERE json_extract(data, '$.Serial') = ?",
                (serial,)
            )

        conn.commit()
        conn.close()

        if affected == 0:
            return False, "Item not found"
        return True, "Item deleted successfully (including inventory item)"
    except Exception as e:
        return False, str(e)

# User Settings Functions
def get_user_page_settings(username, page):
    """Get user settings for a specific page"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT settings FROM user_settings WHERE username = ? AND page = ?",
            (username, page)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row['settings'])
        return {}
    except Exception as e:
        print(f"Error getting user settings: {e}")
        return {}

def save_user_page_settings(username, page, settings):
    """Save user settings for a specific page"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        settings_json = json.dumps(settings)

        # Use INSERT OR REPLACE to handle both insert and update
        cursor.execute('''
            INSERT INTO user_settings (username, page, settings, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(username, page) DO UPDATE SET
                settings = excluded.settings,
                updated_at = CURRENT_TIMESTAMP
        ''', (username, page, settings_json))

        conn.commit()
        conn.close()
        return True, "Settings saved successfully"
    except Exception as e:
        print(f"Error saving user settings: {e}")
        return False, str(e)

if __name__ == '__main__':
    init_database()
    init_inventory_database()
