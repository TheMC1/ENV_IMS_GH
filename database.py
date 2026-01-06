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

    # Create role_permissions table for storing page access by role
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT UNIQUE NOT NULL,
            allowed_pages TEXT NOT NULL DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create activity_logs table for tracking all user actions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT,
            serial TEXT,
            details TEXT,
            before_data TEXT,
            after_data TEXT,
            is_reverted INTEGER DEFAULT 0,
            reverted_by TEXT,
            reverted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create system_settings table for global application settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    ''')

    # Initialize default system settings if not exist
    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE key = 'logging_enabled'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?)",
            ('logging_enabled', '1')
        )

    cursor.execute("SELECT COUNT(*) FROM system_settings WHERE key = 'backup_tracking_enabled'")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?)",
            ('backup_tracking_enabled', '1')
        )

    # Initialize default role permissions if not exist
    default_permissions = {
        'admin': ['dashboard', 'inventory', 'warranties', 'trades', 'reports', 'users', 'settings', 'backups', 'logs'],
        'trader': ['dashboard', 'inventory', 'warranties', 'trades', 'reports', 'settings', 'logs'],
        'ops': ['dashboard', 'inventory', 'warranties', 'reports', 'settings', 'logs'],
        'user': ['dashboard', 'inventory', 'warranties', 'reports', 'settings', 'logs']
    }

    for role, pages in default_permissions.items():
        cursor.execute("SELECT COUNT(*) FROM role_permissions WHERE role = ?", (role,))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO role_permissions (role, allowed_pages) VALUES (?, ?)",
                (role, json.dumps(pages))
            )

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
            vintage TEXT,
            serial TEXT UNIQUE,
            is_custody TEXT,
            is_assigned INTEGER DEFAULT 0,
            trade_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add columns if they don't exist (for existing databases)
    cursor.execute("PRAGMA table_info(inventory)")
    inventory_columns = [column[1] for column in cursor.fetchall()]
    if 'vintage' not in inventory_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN vintage TEXT")
        except:
            pass
    if 'is_assigned' not in inventory_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN is_assigned INTEGER DEFAULT 0")
        except:
            pass
    if 'trade_id' not in inventory_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN trade_id TEXT")
        except:
            pass
    if 'criteria_id' not in inventory_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN criteria_id INTEGER")
        except:
            pass
    if 'criteria_snapshot' not in inventory_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN criteria_snapshot TEXT")
        except:
            pass

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

    # Add reservation columns to inventory table if they don't exist
    cursor.execute("PRAGMA table_info(inventory)")
    inv_columns = [column[1] for column in cursor.fetchall()]

    if 'is_reserved' not in inv_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN is_reserved INTEGER DEFAULT 0")
        except:
            pass
    if 'reserved_for_trade_id' not in inv_columns:
        try:
            cursor.execute("ALTER TABLE inventory ADD COLUMN reserved_for_trade_id TEXT")
        except:
            pass

    # Create trade_criteria table for generic buy/sell positions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('buy', 'sell')),
            quantity_required INTEGER NOT NULL,
            quantity_fulfilled INTEGER DEFAULT 0,
            market TEXT,
            registry TEXT,
            product TEXT,
            project_type TEXT,
            protocol TEXT,
            project_id TEXT,
            vintage_from TEXT,
            vintage_to TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'partial', 'fulfilled', 'cancelled', 'criteria_only')),
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: Add project_id column to trade_criteria if it doesn't exist
    try:
        cursor.execute("ALTER TABLE trade_criteria ADD COLUMN project_id TEXT")
    except:
        pass  # Column already exists

    # Migration: Recreate trade_criteria table with updated CHECK constraint for 'criteria_only' status
    # SQLite doesn't support modifying CHECK constraints, so we need to recreate the table
    try:
        # Check if migration is needed by trying to insert a test value
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trade_criteria'")
        table_def = cursor.fetchone()
        if table_def and 'criteria_only' not in table_def[0]:
            # Need to migrate - create new table with correct constraint
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_criteria_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('buy', 'sell')),
                    quantity_required INTEGER NOT NULL,
                    quantity_fulfilled INTEGER DEFAULT 0,
                    market TEXT,
                    registry TEXT,
                    product TEXT,
                    project_type TEXT,
                    protocol TEXT,
                    project_id TEXT,
                    vintage_from TEXT,
                    vintage_to TEXT,
                    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'partial', 'fulfilled', 'cancelled', 'criteria_only')),
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Copy existing data
            cursor.execute('''
                INSERT INTO trade_criteria_new
                SELECT id, trade_id, direction, quantity_required, quantity_fulfilled,
                       market, registry, product, project_type, protocol, project_id,
                       vintage_from, vintage_to, status, created_by, created_at, updated_at
                FROM trade_criteria
            ''')
            # Drop old table and rename new one
            cursor.execute('DROP TABLE trade_criteria')
            cursor.execute('ALTER TABLE trade_criteria_new RENAME TO trade_criteria')
            conn.commit()
            print("Migrated trade_criteria table to support 'criteria_only' status")
    except Exception as e:
        print(f"trade_criteria migration note: {e}")

    # Create inventory_reservations table to track reservation history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            criteria_id INTEGER,
            serial TEXT NOT NULL,
            reserved_by TEXT NOT NULL,
            reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            released_at TIMESTAMP,
            released_by TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'released', 'delivered')),
            FOREIGN KEY (criteria_id) REFERENCES trade_criteria(id),
            FOREIGN KEY (serial) REFERENCES inventory(serial)
        )
    ''')

    # Create generic_inventory table for buy positions with unknown serials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generic_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            criteria_id INTEGER,
            quantity INTEGER NOT NULL,
            market TEXT,
            registry TEXT,
            product TEXT,
            project_type TEXT,
            protocol TEXT,
            vintage TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'partial', 'fulfilled')),
            fulfilled_quantity INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (criteria_id) REFERENCES trade_criteria(id)
        )
    ''')

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
                   protocol, project_name, vintage, serial, is_custody,
                   is_assigned, trade_id, is_reserved, reserved_for_trade_id
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
                'Vintage': row['vintage'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or '',
                'IsAssigned': 'True' if row['is_assigned'] else 'False',
                'TradeID': row['trade_id'] or '',
                'IsReserved': 'True' if row['is_reserved'] else 'False',
                'ReservedForTradeID': row['reserved_for_trade_id'] or ''
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
        'Vintage',
        'Serial',
        'IsCustody',
        'IsAssigned',
        'TradeID'
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

        # Handle IsAssigned - convert string to integer
        is_assigned_str = clean_data.get('IsAssigned', 'False')
        is_assigned = 1 if is_assigned_str in ['True', 'true', '1', True] else 0

        # Insert into individual columns
        cursor.execute("""
            INSERT INTO inventory (market, registry, product, project_id, project_type,
                                 protocol, project_name, vintage, serial, is_custody,
                                 is_assigned, trade_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clean_data.get('Market', ''),
            clean_data.get('Registry', ''),
            clean_data.get('Product', ''),
            clean_data.get('ProjectID', ''),
            clean_data.get('ProjectType', ''),
            clean_data.get('Protocol', ''),
            clean_data.get('ProjectName', ''),
            clean_data.get('Vintage', ''),
            clean_data.get('Serial', ''),
            clean_data.get('IsCustody', ''),
            is_assigned,
            clean_data.get('TradeID', '')
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

        # Handle IsAssigned - convert string to integer
        is_assigned_str = clean_data.get('IsAssigned', 'False')
        is_assigned = 1 if is_assigned_str in ['True', 'true', '1', True] else 0

        # Update individual columns
        cursor.execute("""
            UPDATE inventory
            SET market = ?, registry = ?, product = ?, project_id = ?, project_type = ?,
                protocol = ?, project_name = ?, vintage = ?, serial = ?, is_custody = ?,
                is_assigned = ?, trade_id = ?,
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
            clean_data.get('Vintage', ''),
            new_serial,
            clean_data.get('IsCustody', ''),
            is_assigned,
            clean_data.get('TradeID', ''),
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
    """Create a backup snapshot of the entire inventory including warranties"""
    # Check if backup tracking is enabled
    if not is_backup_tracking_enabled():
        return True, None  # Silently skip backup when paused

    try:
        # Get all current inventory data
        items = get_all_inventory_items()

        # Get all warranty data
        conn = get_inventory_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM warranties")
        warranty_rows = cursor.fetchall()
        warranties = [dict(row) for row in warranty_rows]

        # Combine inventory and warranty data
        backup_data = {
            'inventory': items,
            'warranties': warranties
        }

        cursor.execute(
            "INSERT INTO inventory_backups (username, action, summary, backup_data) VALUES (?, ?, ?, ?)",
            (username, action, json.dumps(summary) if summary else None, json.dumps(backup_data))
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
    """Restore inventory and warranties from a backup snapshot"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get the backup data
        cursor.execute("SELECT backup_data FROM inventory_backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Backup not found"

        backup_data = json.loads(row['backup_data'])

        # Handle both old format (list) and new format (dict with inventory/warranties)
        if isinstance(backup_data, list):
            # Old format - just inventory items
            backup_items = backup_data
            backup_warranties = []
        else:
            # New format - dict with inventory and warranties
            backup_items = backup_data.get('inventory', [])
            backup_warranties = backup_data.get('warranties', [])

        # Clear current inventory and warranties
        cursor.execute("DELETE FROM warranties")
        cursor.execute("DELETE FROM inventory")

        # Restore inventory items from backup
        for item in backup_items:
            clean_data = {k: v for k, v in item.items() if k != '_row_index'}
            # Handle IsAssigned - convert string to integer
            is_assigned_str = clean_data.get('IsAssigned', 'False')
            is_assigned = 1 if is_assigned_str in ['True', 'true', '1', True] else 0
            cursor.execute("""
                INSERT INTO inventory (market, registry, product, project_id, project_type,
                                     protocol, project_name, vintage, serial, is_custody,
                                     is_assigned, trade_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clean_data.get('Market', ''),
                clean_data.get('Registry', ''),
                clean_data.get('Product', ''),
                clean_data.get('ProjectID', ''),
                clean_data.get('ProjectType', ''),
                clean_data.get('Protocol', ''),
                clean_data.get('ProjectName', ''),
                clean_data.get('Vintage', ''),
                clean_data.get('Serial', ''),
                clean_data.get('IsCustody', ''),
                is_assigned,
                clean_data.get('TradeID', '')
            ))

        # Restore warranty items from backup
        for warranty in backup_warranties:
            # Skip internal fields
            clean_warranty = {k: v for k, v in warranty.items() if k not in ['id', 'created_at', 'updated_at']}
            if clean_warranty.get('serial'):
                cursor.execute("""
                    INSERT INTO warranties (serial, buy_start, buy_end, sell_start, sell_end,
                                          buy_tradeid, sell_tradeid, buy_client, sell_client)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_warranty.get('serial', ''),
                    clean_warranty.get('buy_start', ''),
                    clean_warranty.get('buy_end', ''),
                    clean_warranty.get('sell_start', ''),
                    clean_warranty.get('sell_end', ''),
                    clean_warranty.get('buy_tradeid'),
                    clean_warranty.get('sell_tradeid'),
                    clean_warranty.get('buy_client', ''),
                    clean_warranty.get('sell_client', '')
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
                i.vintage,
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
                'Vintage': row['vintage'] or '',
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
        'Vintage',
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


# Trade Assignment Functions

def assign_inventory_to_trade(serials, trade_id, warranty_data=None, criteria_id=None):
    """
    Assign inventory items to a trade by serial numbers.

    Args:
        serials: List of serial numbers to assign
        trade_id: The trade ID to assign to
        warranty_data: Optional dict with warranty dates to set
            {
                'buy_start': 'YYYY-MM-DD',
                'buy_end': 'YYYY-MM-DD',
                'sell_start': 'YYYY-MM-DD',
                'sell_end': 'YYYY-MM-DD',
                'buy_client': 'client name',
                'sell_client': 'client name'
            }
        criteria_id: Optional criteria ID that this inventory was assigned through

    Returns:
        (success, message, count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # If criteria_id is provided, fetch and store the criteria snapshot
        criteria_snapshot_json = None
        if criteria_id:
            cursor.execute("""
                SELECT id, trade_id, direction, quantity_required, market, registry, product,
                       project_type, protocol, project_id, vintage_from, vintage_to, status
                FROM trade_criteria
                WHERE id = ?
            """, (criteria_id,))
            crit = cursor.fetchone()
            if crit:
                criteria_snapshot = {
                    'trade_id': crit['trade_id'],
                    'direction': crit['direction'],
                    'market': crit['market'],
                    'registry': crit['registry'],
                    'product': crit['product'],
                    'project_type': crit['project_type'],
                    'protocol': crit['protocol'],
                    'project_id': crit['project_id'],
                    'vintage_from': crit['vintage_from'],
                    'vintage_to': crit['vintage_to']
                }
                criteria_snapshot_json = json.dumps(criteria_snapshot)

        assigned_count = 0

        for serial in serials:
            # Update inventory record with criteria_id and snapshot if provided
            cursor.execute("""
                UPDATE inventory
                SET is_assigned = 1, trade_id = ?, criteria_id = ?, criteria_snapshot = ?, updated_at = CURRENT_TIMESTAMP
                WHERE serial = ?
            """, (trade_id, criteria_id, criteria_snapshot_json, serial))

            if cursor.rowcount > 0:
                assigned_count += 1

                # Update warranty if warranty_data provided
                if warranty_data:
                    cursor.execute("""
                        UPDATE warranties
                        SET buy_start = COALESCE(?, buy_start),
                            buy_end = COALESCE(?, buy_end),
                            sell_start = COALESCE(?, sell_start),
                            sell_end = COALESCE(?, sell_end),
                            buy_tradeid = COALESCE(?, buy_tradeid),
                            sell_tradeid = COALESCE(?, sell_tradeid),
                            buy_client = COALESCE(?, buy_client),
                            sell_client = COALESCE(?, sell_client),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE serial = ?
                    """, (
                        warranty_data.get('buy_start'),
                        warranty_data.get('buy_end'),
                        warranty_data.get('sell_start'),
                        warranty_data.get('sell_end'),
                        trade_id if warranty_data.get('set_buy_tradeid') else None,
                        trade_id if warranty_data.get('set_sell_tradeid') else None,
                        warranty_data.get('buy_client'),
                        warranty_data.get('sell_client'),
                        serial
                    ))

        conn.commit()
        conn.close()

        return True, f"Successfully assigned {assigned_count} item(s) to trade {trade_id}", assigned_count
    except Exception as e:
        return False, str(e), 0


def unassign_inventory_from_trade(serials, username=None, restore_criteria=True):
    """
    Unassign inventory items from their trades and optionally restore criteria.

    Args:
        serials: List of serial numbers to unassign
        username: Username for logging criteria restoration
        restore_criteria: Whether to restore criteria quantity (default True)

    Returns:
        (success, message, count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # First, get criteria info for all serials BEFORE unassigning
        criteria_to_restore = {}  # {criteria_id: {'count': N, 'snapshot': {...}}}

        if restore_criteria:
            for serial in serials:
                cursor.execute("""
                    SELECT criteria_id, trade_id, criteria_snapshot FROM inventory WHERE serial = ?
                """, (serial,))
                inv = cursor.fetchone()

                if inv and inv['criteria_id']:
                    criteria_id = inv['criteria_id']
                    trade_id = inv['trade_id']
                    stored_snapshot = inv['criteria_snapshot']

                    if criteria_id not in criteria_to_restore:
                        # Get criteria details (may be deleted)
                        cursor.execute("""
                            SELECT id, trade_id, direction, quantity_required, market, registry, product,
                                   project_type, protocol, project_id, vintage_from, vintage_to, status
                            FROM trade_criteria
                            WHERE id = ?
                        """, (criteria_id,))
                        crit = cursor.fetchone()

                        if crit:
                            # Criteria still exists - use current values
                            criteria_to_restore[criteria_id] = {
                                'count': 0,
                                'snapshot': dict(crit)
                            }
                        elif stored_snapshot:
                            # Criteria was deleted - use the stored snapshot from when it was assigned
                            try:
                                snapshot_dict = json.loads(stored_snapshot)
                                criteria_to_restore[criteria_id] = {
                                    'count': 0,
                                    'snapshot': snapshot_dict
                                }
                            except (json.JSONDecodeError, TypeError):
                                pass  # Invalid snapshot, skip restoration

                    if criteria_id in criteria_to_restore:
                        criteria_to_restore[criteria_id]['count'] += 1

        unassigned_count = 0

        for serial in serials:
            cursor.execute("""
                UPDATE inventory
                SET is_assigned = 0, trade_id = NULL, criteria_id = NULL, criteria_snapshot = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE serial = ?
            """, (serial,))

            if cursor.rowcount > 0:
                unassigned_count += 1

        conn.commit()
        conn.close()

        # Restore criteria quantities after unassigning
        if restore_criteria and criteria_to_restore:
            for criteria_id, info in criteria_to_restore.items():
                restore_criteria_on_unassign(
                    criteria_id,
                    info['count'],
                    username or 'system',
                    info['snapshot']
                )

        return True, f"Successfully unassigned {unassigned_count} item(s)", unassigned_count
    except Exception as e:
        return False, str(e), 0


def get_inventory_by_trade(trade_id):
    """Get all inventory items assigned to a specific trade"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, project_name, vintage, serial, is_custody,
                   is_assigned, trade_id
            FROM inventory
            WHERE trade_id = ?
            ORDER BY id
        """, (trade_id,))
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
                'Vintage': row['vintage'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or '',
                'IsAssigned': 'True' if row['is_assigned'] else 'False',
                'TradeID': row['trade_id'] or ''
            }
            items.append(item_data)

        return items
    except Exception as e:
        print(f"Error getting inventory by trade: {e}")
        return []


def get_unassigned_inventory():
    """Get all unassigned inventory items"""
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, project_name, vintage, serial, is_custody,
                   is_assigned, trade_id
            FROM inventory
            WHERE is_assigned = 0 OR is_assigned IS NULL
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
                'Vintage': row['vintage'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or '',
                'IsAssigned': 'False',
                'TradeID': ''
            }
            items.append(item_data)

        return items
    except Exception as e:
        print(f"Error getting unassigned inventory: {e}")
        return []


def create_serials_for_trade(serials, trade_id, inventory_data, warranty_data):
    """
    Create new inventory items and assign them to a trade with BUY warranty info.

    Args:
        serials: List of serial numbers to create
        trade_id: Trade ID to assign to
        inventory_data: Dict with inventory metadata (market, registry, product, etc.)
        warranty_data: Dict with buy warranty info (buy_client, buy_start, buy_end)

    Returns:
        (success, message, created_count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        created_count = 0
        skipped_serials = []

        for serial in serials:
            # Check if serial already exists
            cursor.execute("SELECT id FROM inventory WHERE serial = ?", (serial,))
            if cursor.fetchone():
                skipped_serials.append(serial)
                continue

            # Insert new inventory item
            cursor.execute("""
                INSERT INTO inventory (market, registry, product, project_id, project_type,
                                     protocol, project_name, vintage, serial, is_custody,
                                     is_assigned, trade_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                inventory_data.get('market', ''),
                inventory_data.get('registry', ''),
                inventory_data.get('product', ''),
                inventory_data.get('project_id', ''),
                inventory_data.get('project_type', ''),
                inventory_data.get('protocol', ''),
                inventory_data.get('project_name', ''),
                inventory_data.get('vintage', ''),
                serial,
                inventory_data.get('is_custody', 'Yes'),
                trade_id
            ))

            # Create warranty record with BUY info
            cursor.execute("""
                INSERT OR REPLACE INTO warranties (
                    serial, buy_tradeid, buy_client, buy_start, buy_end
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                serial,
                trade_id,
                warranty_data.get('buy_client', ''),
                warranty_data.get('buy_start', ''),
                warranty_data.get('buy_end', '')
            ))

            created_count += 1

        conn.commit()
        conn.close()

        if skipped_serials:
            return True, f"Created {created_count} serial(s). Skipped {len(skipped_serials)} existing serial(s)", created_count
        return True, f"Successfully created {created_count} serial(s)", created_count
    except Exception as e:
        return False, str(e), 0


# Role Permissions Functions
def get_all_role_permissions():
    """Get all role permissions"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role, allowed_pages FROM role_permissions ORDER BY role")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for row in rows:
            result[row['role']] = json.loads(row['allowed_pages'])
        return result
    except Exception as e:
        print(f"Error getting role permissions: {e}")
        return {}


def get_role_permissions(role):
    """Get permissions for a specific role"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT allowed_pages FROM role_permissions WHERE role = ?", (role,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row['allowed_pages'])
        return []
    except Exception as e:
        print(f"Error getting role permissions: {e}")
        return []


def update_role_permissions(role, allowed_pages):
    """Update permissions for a role"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO role_permissions (role, allowed_pages, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (role, json.dumps(allowed_pages))
        )
        conn.commit()
        conn.close()
        return True, "Permissions updated successfully"
    except Exception as e:
        return False, str(e)


def check_page_access(username, page):
    """Check if a user has access to a specific page"""
    try:
        user = get_user_by_username(username)
        if not user:
            return False

        role = user['role']

        # Admin always has access to everything
        if role == 'admin':
            return True

        allowed_pages = get_role_permissions(role)
        return page in allowed_pages
    except Exception as e:
        print(f"Error checking page access: {e}")
        return False


def get_available_pages():
    """Get list of all available pages in the system"""
    return [
        {'id': 'dashboard', 'name': 'Dashboard', 'description': 'System overview and analytics'},
        {'id': 'inventory', 'name': 'Inventory', 'description': 'Manage inventory items'},
        {'id': 'warranties', 'name': 'Warranties', 'description': 'Manage warranty information'},
        {'id': 'trades', 'name': 'Trades', 'description': 'Manage trades and assignments'},
        {'id': 'reports', 'name': 'Reports', 'description': 'View reports and statistics'},
        {'id': 'settings', 'name': 'Settings', 'description': 'User settings and preferences'},
        {'id': 'users', 'name': 'User Management', 'description': 'Manage users (admin only)'},
        {'id': 'backups', 'name': 'Backups', 'description': 'System backups (admin only)'},
        {'id': 'logs', 'name': 'Activity Logs', 'description': 'View system activity logs'}
    ]


def get_available_roles():
    """Get list of available roles"""
    return ['admin', 'trader', 'ops', 'user']


# =============================================================================
# SYSTEM SETTINGS FUNCTIONS
# =============================================================================

def get_system_setting(key, default=None):
    """
    Get a system setting value by key.

    Args:
        key: The setting key to retrieve
        default: Default value if key not found

    Returns:
        The setting value or default
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else default
    except Exception:
        return default


def set_system_setting(key, value, username=None):
    """
    Set a system setting value.

    Args:
        key: The setting key
        value: The value to set
        username: User making the change (optional)

    Returns:
        (success, message)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_settings (key, value, updated_at, updated_by)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
        """, (key, value, username))
        conn.commit()
        conn.close()
        return True, "Setting updated"
    except Exception as e:
        return False, str(e)


def is_logging_enabled():
    """Check if activity logging is enabled."""
    return get_system_setting('logging_enabled', '1') == '1'


def set_logging_enabled(enabled, username=None):
    """
    Enable or disable activity logging.

    Args:
        enabled: Boolean - True to enable, False to disable
        username: User making the change

    Returns:
        (success, message)
    """
    return set_system_setting('logging_enabled', '1' if enabled else '0', username)


def is_backup_tracking_enabled():
    """Check if backup tracking is enabled."""
    return get_system_setting('backup_tracking_enabled', '1') == '1'


def set_backup_tracking_enabled(enabled, username=None):
    """
    Enable or disable backup tracking.

    Args:
        enabled: Boolean - True to enable, False to disable
        username: User making the change

    Returns:
        (success, message)
    """
    return set_system_setting('backup_tracking_enabled', '1' if enabled else '0', username)


# =============================================================================
# ACTIVITY LOGGING FUNCTIONS
# =============================================================================

def log_activity(username, action_type, target_type, target_id=None, serial=None,
                 details=None, before_data=None, after_data=None):
    """
    Log an activity to the activity_logs table.

    Args:
        username: The user performing the action
        action_type: Type of action (add, update, delete, import, restore, login, etc.)
        target_type: Type of target (inventory, warranty, user, backup, system)
        target_id: ID of the target record (optional)
        serial: Serial number if applicable (optional)
        details: Human-readable description of the action
        before_data: JSON string of data before the change (optional)
        after_data: JSON string of data after the change (optional)

    Returns:
        (success, log_id or error_message)
    """
    # Check if logging is enabled (paused)
    if not is_logging_enabled():
        return True, None  # Silently skip logging when paused

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activity_logs
            (username, action_type, target_type, target_id, serial, details, before_data, after_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username,
            action_type,
            target_type,
            target_id,
            serial,
            details,
            json.dumps(before_data) if before_data else None,
            json.dumps(after_data) if after_data else None
        ))

        conn.commit()
        log_id = cursor.lastrowid
        conn.close()

        return True, log_id
    except Exception as e:
        return False, str(e)


def get_activity_logs(filters=None, limit=500, offset=0):
    """
    Get activity logs with optional filtering.

    Args:
        filters: Dict with optional keys: username, action_type, target_type,
                 date_from, date_to, serial, is_reverted
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of activity log records
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM activity_logs WHERE 1=1"
        params = []

        if filters:
            if filters.get('username'):
                query += " AND username = ?"
                params.append(filters['username'])
            if filters.get('action_type'):
                query += " AND action_type = ?"
                params.append(filters['action_type'])
            if filters.get('target_type'):
                query += " AND target_type = ?"
                params.append(filters['target_type'])
            if filters.get('date_from'):
                query += " AND date(created_at) >= date(?)"
                params.append(filters['date_from'])
            if filters.get('date_to'):
                query += " AND date(created_at) <= date(?)"
                params.append(filters['date_to'])
            if filters.get('serial'):
                query += " AND serial LIKE ?"
                params.append(f"%{filters['serial']}%")
            if filters.get('is_reverted') is not None:
                query += " AND is_reverted = ?"
                params.append(1 if filters['is_reverted'] else 0)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        result = []
        for log in logs:
            log_dict = dict(log)
            # Parse JSON fields
            if log_dict.get('before_data'):
                try:
                    log_dict['before_data'] = json.loads(log_dict['before_data'])
                except:
                    pass
            if log_dict.get('after_data'):
                try:
                    log_dict['after_data'] = json.loads(log_dict['after_data'])
                except:
                    pass
            result.append(log_dict)

        return result
    except Exception as e:
        print(f"Error getting activity logs: {e}")
        return []


def get_activity_log_by_id(log_id):
    """Get a specific activity log by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activity_logs WHERE id = ?", (log_id,))
        log = cursor.fetchone()
        conn.close()

        if log:
            log_dict = dict(log)
            if log_dict.get('before_data'):
                try:
                    log_dict['before_data'] = json.loads(log_dict['before_data'])
                except:
                    pass
            if log_dict.get('after_data'):
                try:
                    log_dict['after_data'] = json.loads(log_dict['after_data'])
                except:
                    pass
            return log_dict
        return None
    except Exception as e:
        print(f"Error getting activity log: {e}")
        return None


def mark_activity_reverted(log_id, reverted_by):
    """Mark an activity log as reverted"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE activity_logs
            SET is_reverted = 1, reverted_by = ?, reverted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reverted_by, log_id))

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0
    except Exception as e:
        print(f"Error marking activity as reverted: {e}")
        return False


def clear_activity_reverted(log_id):
    """Clear the reverted status of an activity log (for redo)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE activity_logs
            SET is_reverted = 0, reverted_by = NULL, reverted_at = NULL
            WHERE id = ?
        """, (log_id,))

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0
    except Exception as e:
        print(f"Error clearing activity reverted status: {e}")
        return False


def get_activity_log_stats():
    """Get statistics about activity logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get counts by action type
        cursor.execute("""
            SELECT action_type, COUNT(*) as count
            FROM activity_logs
            GROUP BY action_type
        """)
        action_counts = {row['action_type']: row['count'] for row in cursor.fetchall()}

        # Get counts by target type
        cursor.execute("""
            SELECT target_type, COUNT(*) as count
            FROM activity_logs
            GROUP BY target_type
        """)
        target_counts = {row['target_type']: row['count'] for row in cursor.fetchall()}

        # Get counts by user
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM activity_logs
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        user_counts = {row['username']: row['count'] for row in cursor.fetchall()}

        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM activity_logs")
        total = cursor.fetchone()['total']

        # Get reverted count
        cursor.execute("SELECT COUNT(*) as reverted FROM activity_logs WHERE is_reverted = 1")
        reverted = cursor.fetchone()['reverted']

        conn.close()

        return {
            'total': total,
            'reverted': reverted,
            'by_action': action_counts,
            'by_target': target_counts,
            'by_user': user_counts
        }
    except Exception as e:
        print(f"Error getting activity stats: {e}")
        return {}


def get_distinct_log_values():
    """Get distinct values for filter dropdowns"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT username FROM activity_logs ORDER BY username")
        usernames = [row['username'] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT action_type FROM activity_logs ORDER BY action_type")
        action_types = [row['action_type'] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT target_type FROM activity_logs ORDER BY target_type")
        target_types = [row['target_type'] for row in cursor.fetchall()]

        conn.close()

        return {
            'usernames': usernames,
            'action_types': action_types,
            'target_types': target_types
        }
    except Exception as e:
        print(f"Error getting distinct log values: {e}")
        return {'usernames': [], 'action_types': [], 'target_types': []}


# =============================================================================
# INVENTORY RESERVATION FUNCTIONS (for Sell Generic)
# =============================================================================

def get_inventory_by_criteria(criteria, exclude_reserved=True, exclude_assigned=False):
    """
    Query inventory items matching the given criteria.

    Args:
        criteria: dict with optional keys: market, registry, product, project_type,
                  protocol, vintage_from, vintage_to
        exclude_reserved: if True, exclude items already reserved
        exclude_assigned: if True, exclude items already assigned to trades

    Returns:
        List of matching inventory items
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, project_name, vintage, serial, is_custody,
                   is_assigned, trade_id, is_reserved, reserved_for_trade_id
            FROM inventory
            WHERE 1=1
        """
        params = []

        if criteria.get('market'):
            query += " AND market = ?"
            params.append(criteria['market'])
        if criteria.get('registry'):
            query += " AND registry = ?"
            params.append(criteria['registry'])
        if criteria.get('product'):
            query += " AND product = ?"
            params.append(criteria['product'])
        if criteria.get('project_type'):
            query += " AND project_type = ?"
            params.append(criteria['project_type'])
        if criteria.get('protocol'):
            query += " AND protocol = ?"
            params.append(criteria['protocol'])
        if criteria.get('project_id'):
            query += " AND project_id = ?"
            params.append(criteria['project_id'])
        if criteria.get('vintage_from'):
            query += " AND vintage >= ?"
            params.append(criteria['vintage_from'])
        if criteria.get('vintage_to'):
            query += " AND vintage <= ?"
            params.append(criteria['vintage_to'])

        if exclude_reserved:
            query += " AND (is_reserved = 0 OR is_reserved IS NULL)"
        if exclude_assigned:
            query += " AND (is_assigned = 0 OR is_assigned IS NULL)"

        query += " ORDER BY vintage, serial"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            items.append({
                '_row_index': row['id'],
                'Market': row['market'] or '',
                'Registry': row['registry'] or '',
                'Product': row['product'] or '',
                'ProjectID': row['project_id'] or '',
                'ProjectType': row['project_type'] or '',
                'Protocol': row['protocol'] or '',
                'ProjectName': row['project_name'] or '',
                'Vintage': row['vintage'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or '',
                'IsAssigned': 'True' if row['is_assigned'] else 'False',
                'TradeID': row['trade_id'] or '',
                'IsReserved': 'True' if row['is_reserved'] else 'False',
                'ReservedForTradeID': row['reserved_for_trade_id'] or ''
            })

        return items
    except Exception as e:
        print(f"Error querying inventory by criteria: {e}")
        return []


def reserve_inventory(serials, trade_id, username, criteria_id=None):
    """
    Reserve inventory items for a trade.

    Args:
        serials: list of serial numbers to reserve
        trade_id: the trade ID to reserve for
        username: user making the reservation
        criteria_id: optional link to trade_criteria record

    Returns:
        (success, message, count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        reserved_count = 0
        already_reserved = []
        not_found = []

        for serial in serials:
            # Check if item exists and is not already reserved
            cursor.execute("""
                SELECT id, is_reserved, reserved_for_trade_id
                FROM inventory WHERE serial = ?
            """, (serial,))
            row = cursor.fetchone()

            if not row:
                not_found.append(serial)
                continue

            if row['is_reserved']:
                already_reserved.append(serial)
                continue

            # Reserve the item
            cursor.execute("""
                UPDATE inventory SET
                    is_reserved = 1,
                    reserved_for_trade_id = ?
                WHERE serial = ?
            """, (trade_id, serial))

            # Record in reservation history
            cursor.execute("""
                INSERT INTO inventory_reservations
                (trade_id, criteria_id, serial, reserved_by, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (trade_id, criteria_id, serial, username))

            reserved_count += 1

        conn.commit()
        conn.close()

        message = f"Reserved {reserved_count} item(s) for trade {trade_id}"
        if already_reserved:
            message += f". {len(already_reserved)} already reserved."
        if not_found:
            message += f". {len(not_found)} not found."

        return True, message, reserved_count
    except Exception as e:
        print(f"Error reserving inventory: {e}")
        return False, str(e), 0


def release_reservation(serials, username):
    """
    Release reservation on inventory items.

    Args:
        serials: list of serial numbers to release
        username: user releasing the reservation

    Returns:
        (success, message, count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        released_count = 0

        for serial in serials:
            # Update inventory
            cursor.execute("""
                UPDATE inventory SET
                    is_reserved = 0,
                    reserved_for_trade_id = NULL
                WHERE serial = ? AND is_reserved = 1
            """, (serial,))

            if cursor.rowcount > 0:
                released_count += 1

                # Update reservation history
                cursor.execute("""
                    UPDATE inventory_reservations SET
                        status = 'released',
                        released_at = CURRENT_TIMESTAMP,
                        released_by = ?
                    WHERE serial = ? AND status = 'active'
                """, (username, serial))

        conn.commit()
        conn.close()

        return True, f"Released {released_count} reservation(s)", released_count
    except Exception as e:
        print(f"Error releasing reservations: {e}")
        return False, str(e), 0


def get_reserved_inventory(trade_id=None):
    """
    Get all reserved inventory items, optionally filtered by trade.

    Args:
        trade_id: optional trade ID to filter by

    Returns:
        List of reserved inventory items
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, project_name, vintage, serial, is_custody,
                   is_assigned, trade_id, is_reserved, reserved_for_trade_id
            FROM inventory
            WHERE is_reserved = 1
        """
        params = []

        if trade_id:
            query += " AND reserved_for_trade_id = ?"
            params.append(trade_id)

        query += " ORDER BY serial"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            items.append({
                '_row_index': row['id'],
                'Market': row['market'] or '',
                'Registry': row['registry'] or '',
                'Product': row['product'] or '',
                'ProjectID': row['project_id'] or '',
                'ProjectType': row['project_type'] or '',
                'Protocol': row['protocol'] or '',
                'ProjectName': row['project_name'] or '',
                'Vintage': row['vintage'] or '',
                'Serial': row['serial'] or '',
                'IsCustody': row['is_custody'] or '',
                'IsAssigned': 'True' if row['is_assigned'] else 'False',
                'TradeID': row['trade_id'] or '',
                'IsReserved': 'True',
                'ReservedForTradeID': row['reserved_for_trade_id'] or ''
            })

        return items
    except Exception as e:
        print(f"Error getting reserved inventory: {e}")
        return []


def mark_reservation_delivered(serials, username):
    """
    Mark reserved items as delivered (assigned to trade).

    Args:
        serials: list of serial numbers
        username: user performing the delivery

    Returns:
        (success, message, count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        delivered_count = 0

        for serial in serials:
            # Get the reserved trade ID
            cursor.execute("""
                SELECT reserved_for_trade_id FROM inventory
                WHERE serial = ? AND is_reserved = 1
            """, (serial,))
            row = cursor.fetchone()

            if row and row['reserved_for_trade_id']:
                trade_id = row['reserved_for_trade_id']

                # Update inventory - assign to trade and clear reservation
                cursor.execute("""
                    UPDATE inventory SET
                        is_assigned = 1,
                        trade_id = ?,
                        is_reserved = 0,
                        reserved_for_trade_id = NULL
                    WHERE serial = ?
                """, (trade_id, serial))

                # Update reservation history
                cursor.execute("""
                    UPDATE inventory_reservations SET
                        status = 'delivered',
                        released_at = CURRENT_TIMESTAMP,
                        released_by = ?
                    WHERE serial = ? AND status = 'active'
                """, (username, serial))

                delivered_count += 1

        conn.commit()
        conn.close()

        return True, f"Delivered {delivered_count} item(s)", delivered_count
    except Exception as e:
        print(f"Error marking reservation as delivered: {e}")
        return False, str(e), 0


# =============================================================================
# TRADE CRITERIA FUNCTIONS (for Generic Buy/Sell)
# =============================================================================

def create_trade_criteria(trade_id, direction, quantity, criteria, username):
    """
    Create a trade criteria record for generic buy/sell.

    Args:
        trade_id: the trade ID
        direction: 'buy' or 'sell'
        quantity: quantity required
        criteria: dict with optional keys: market, registry, product, project_type,
                  protocol, vintage_from, vintage_to
        username: user creating the criteria

    Returns:
        (success, criteria_id or error message)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trade_criteria
            (trade_id, direction, quantity_required, market, registry, product,
             project_type, protocol, vintage_from, vintage_to, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            direction,
            quantity,
            criteria.get('market'),
            criteria.get('registry'),
            criteria.get('product'),
            criteria.get('project_type'),
            criteria.get('protocol'),
            criteria.get('vintage_from'),
            criteria.get('vintage_to'),
            username
        ))

        criteria_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return True, criteria_id
    except Exception as e:
        print(f"Error creating trade criteria: {e}")
        return False, str(e)


def get_trade_criteria(trade_id=None, criteria_id=None, direction=None, status=None):
    """
    Get trade criteria records.

    Args:
        trade_id: optional filter by trade ID
        criteria_id: optional filter by criteria ID
        direction: optional filter by direction ('buy' or 'sell')
        status: optional filter by status

    Returns:
        List of trade criteria records
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM trade_criteria WHERE 1=1"
        params = []

        if trade_id:
            query += " AND trade_id = ?"
            params.append(trade_id)
        if criteria_id:
            query += " AND id = ?"
            params.append(criteria_id)
        if direction:
            query += " AND direction = ?"
            params.append(direction)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting trade criteria: {e}")
        return []


def update_trade_criteria_fulfillment(criteria_id, quantity_fulfilled):
    """
    Update the fulfilled quantity for a trade criteria.

    Args:
        criteria_id: the criteria ID
        quantity_fulfilled: new fulfilled quantity

    Returns:
        (success, message)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get current criteria
        cursor.execute("SELECT quantity_required FROM trade_criteria WHERE id = ?", (criteria_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Criteria not found"

        quantity_required = row['quantity_required']

        # Determine new status
        if quantity_fulfilled >= quantity_required:
            status = 'fulfilled'
        elif quantity_fulfilled > 0:
            status = 'partial'
        else:
            status = 'pending'

        cursor.execute("""
            UPDATE trade_criteria SET
                quantity_fulfilled = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (quantity_fulfilled, status, criteria_id))

        conn.commit()
        conn.close()

        return True, f"Updated to {quantity_fulfilled}/{quantity_required} ({status})"
    except Exception as e:
        print(f"Error updating trade criteria fulfillment: {e}")
        return False, str(e)


def cancel_trade_criteria(criteria_id, username):
    """
    Cancel a trade criteria and release any reservations.

    Args:
        criteria_id: the criteria ID
        username: user cancelling

    Returns:
        (success, message)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Update criteria status
        cursor.execute("""
            UPDATE trade_criteria SET
                status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (criteria_id,))

        # Release any reservations linked to this criteria
        cursor.execute("""
            SELECT serial FROM inventory_reservations
            WHERE criteria_id = ? AND status = 'active'
        """, (criteria_id,))
        reserved_serials = [row['serial'] for row in cursor.fetchall()]

        conn.commit()
        conn.close()

        # Release the reservations
        if reserved_serials:
            release_reservation(reserved_serials, username)

        return True, f"Cancelled criteria and released {len(reserved_serials)} reservation(s)"
    except Exception as e:
        print(f"Error cancelling trade criteria: {e}")
        return False, str(e)


# =============================================================================
# GENERIC INVENTORY FUNCTIONS (for Buy Generic)
# =============================================================================

def create_generic_inventory(trade_id, quantity, criteria, username, criteria_id=None):
    """
    Create a generic inventory position for a buy trade with unknown serials.

    Args:
        trade_id: the trade ID
        quantity: expected quantity
        criteria: dict with expected attributes
        username: user creating the position
        criteria_id: optional link to trade_criteria record

    Returns:
        (success, generic_id or error message)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO generic_inventory
            (trade_id, criteria_id, quantity, market, registry, product,
             project_type, protocol, vintage, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            criteria_id,
            quantity,
            criteria.get('market'),
            criteria.get('registry'),
            criteria.get('product'),
            criteria.get('project_type'),
            criteria.get('protocol'),
            criteria.get('vintage'),
            username
        ))

        generic_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return True, generic_id
    except Exception as e:
        print(f"Error creating generic inventory: {e}")
        return False, str(e)


def get_generic_inventory(trade_id=None, status=None):
    """
    Get generic inventory positions.

    Args:
        trade_id: optional filter by trade ID
        status: optional filter by status

    Returns:
        List of generic inventory records
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM generic_inventory WHERE 1=1"
        params = []

        if trade_id:
            query += " AND trade_id = ?"
            params.append(trade_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting generic inventory: {e}")
        return []


def fulfill_generic_inventory(generic_id, serials, username):
    """
    Fulfill a generic inventory position with actual serials.

    Args:
        generic_id: the generic inventory ID
        serials: list of actual serial numbers to fulfill with
        username: user performing fulfillment

    Returns:
        (success, message, fulfilled_count)
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get generic inventory record
        cursor.execute("SELECT * FROM generic_inventory WHERE id = ?", (generic_id,))
        generic = cursor.fetchone()

        if not generic:
            conn.close()
            return False, "Generic inventory not found", 0

        trade_id = generic['trade_id']
        current_fulfilled = generic['fulfilled_quantity'] or 0
        quantity_needed = generic['quantity']

        fulfilled_count = 0

        for serial in serials:
            if current_fulfilled + fulfilled_count >= quantity_needed:
                break

            # Assign the inventory item to the trade
            cursor.execute("""
                UPDATE inventory SET
                    is_assigned = 1,
                    trade_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE serial = ? AND (is_assigned = 0 OR is_assigned IS NULL)
            """, (trade_id, serial))

            if cursor.rowcount > 0:
                fulfilled_count += 1

        # Update generic inventory
        new_fulfilled = current_fulfilled + fulfilled_count
        if new_fulfilled >= quantity_needed:
            status = 'fulfilled'
        elif new_fulfilled > 0:
            status = 'partial'
        else:
            status = 'pending'

        cursor.execute("""
            UPDATE generic_inventory SET
                fulfilled_quantity = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_fulfilled, status, generic_id))

        # Also update linked trade_criteria if exists
        if generic['criteria_id']:
            cursor.execute("""
                UPDATE trade_criteria SET
                    quantity_fulfilled = quantity_fulfilled + ?,
                    status = CASE
                        WHEN quantity_fulfilled + ? >= quantity_required THEN 'fulfilled'
                        WHEN quantity_fulfilled + ? > 0 THEN 'partial'
                        ELSE 'pending'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (fulfilled_count, fulfilled_count, fulfilled_count, generic['criteria_id']))

        conn.commit()
        conn.close()

        return True, f"Fulfilled {fulfilled_count} item(s). Total: {new_fulfilled}/{quantity_needed}", fulfilled_count
    except Exception as e:
        print(f"Error fulfilling generic inventory: {e}")
        return False, str(e), 0


def get_pending_generic_positions():
    """
    Get all pending or partially fulfilled generic positions.

    Returns:
        List of generic inventory records that need fulfillment
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.*,
                   (g.quantity - COALESCE(g.fulfilled_quantity, 0)) as remaining
            FROM generic_inventory g
            WHERE g.status IN ('pending', 'partial')
            ORDER BY g.created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting pending generic positions: {e}")
        return []


def get_reservation_summary():
    """
    Get a summary of all reservations grouped by trade.

    Returns:
        Dict with trade_id keys and reservation counts/details
    """
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT reserved_for_trade_id as trade_id,
                   COUNT(*) as reserved_count
            FROM inventory
            WHERE is_reserved = 1
            GROUP BY reserved_for_trade_id
        """)
        rows = cursor.fetchall()
        conn.close()

        return {row['trade_id']: row['reserved_count'] for row in rows}
    except Exception as e:
        print(f"Error getting reservation summary: {e}")
        return {}


# =============================================================================
# CRITERIA ALLOCATION OPTIMIZER
# =============================================================================

def check_inventory_matches_criteria(item, criteria):
    """
    Check if an inventory item matches the given criteria.

    Args:
        item: dict with inventory item data
        criteria: dict with criteria fields

    Returns:
        True if item matches all specified criteria
    """
    # Check each criteria field
    if criteria.get('market') and item.get('market') != criteria.get('market'):
        return False
    if criteria.get('registry') and item.get('registry') != criteria.get('registry'):
        return False
    if criteria.get('product') and item.get('product') != criteria.get('product'):
        return False
    if criteria.get('project_type') and item.get('project_type') != criteria.get('project_type'):
        return False
    if criteria.get('protocol') and item.get('protocol') != criteria.get('protocol'):
        return False
    if criteria.get('project_id') and item.get('project_id') != criteria.get('project_id'):
        return False

    # Check vintage range
    item_vintage = item.get('vintage', '')
    if criteria.get('vintage_from') and item_vintage:
        if str(item_vintage) < str(criteria.get('vintage_from')):
            return False
    if criteria.get('vintage_to') and item_vintage:
        if str(item_vintage) > str(criteria.get('vintage_to')):
            return False

    return True


def get_available_after_criteria_claims(search_criteria):
    """
    Calculate the true available inventory count after accounting for
    Generic Allocation (criteria-only) claims.

    Uses FIFO allocation simulation to determine how much inventory
    is claimed by existing criteria-only allocations.

    Args:
        search_criteria: dict with search criteria (vintage_from, vintage_to,
                        registry, product, project_type, protocol, project_id)

    Returns:
        dict with:
        - 'total_matching': Total inventory matching search criteria (not reserved/assigned)
        - 'claimed_by_criteria': Amount claimed by existing Generic Allocations
        - 'available': True available after claims
        - 'criteria_claims': List of criteria claiming this inventory
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get all available inventory matching search criteria (not reserved, not assigned)
        query = """
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, vintage, serial
            FROM inventory
            WHERE (is_reserved = 0 OR is_reserved IS NULL)
              AND (is_assigned = 0 OR is_assigned IS NULL)
        """
        params = []

        if search_criteria.get('registry'):
            query += " AND registry = ?"
            params.append(search_criteria['registry'])
        if search_criteria.get('product'):
            query += " AND product = ?"
            params.append(search_criteria['product'])
        if search_criteria.get('project_type'):
            query += " AND project_type = ?"
            params.append(search_criteria['project_type'])
        if search_criteria.get('protocol'):
            query += " AND protocol = ?"
            params.append(search_criteria['protocol'])
        if search_criteria.get('project_id'):
            query += " AND project_id = ?"
            params.append(search_criteria['project_id'])
        if search_criteria.get('vintage_from'):
            query += " AND vintage >= ?"
            params.append(search_criteria['vintage_from'])
        if search_criteria.get('vintage_to'):
            query += " AND vintage <= ?"
            params.append(search_criteria['vintage_to'])

        query += " ORDER BY vintage, serial"
        cursor.execute(query, params)
        matching_inventory = [dict(row) for row in cursor.fetchall()]
        total_matching = len(matching_inventory)

        if total_matching == 0:
            conn.close()
            return {
                'total_matching': 0,
                'claimed_by_criteria': 0,
                'available': 0,
                'criteria_claims': []
            }

        # Get all active criteria-only allocations (FIFO order)
        cursor.execute("""
            SELECT * FROM trade_criteria
            WHERE status = 'criteria_only' AND direction = 'sell'
            ORDER BY created_at ASC
        """)
        all_criteria = [dict(row) for row in cursor.fetchall()]
        conn.close()
        conn = None

        if not all_criteria:
            return {
                'total_matching': total_matching,
                'claimed_by_criteria': 0,
                'available': total_matching,
                'criteria_claims': []
            }

        # Simulate FIFO allocation
        allocated_ids = set()
        item_claims = {}  # Maps item_id to claiming trade_id
        criteria_claims = []

        for crit in all_criteria:
            # Find inventory items that match this criteria AND our search criteria
            matching_for_crit = []
            for item in matching_inventory:
                if item['id'] not in allocated_ids:
                    if check_inventory_matches_criteria(item, crit):
                        matching_for_crit.append(item['id'])

            # This criteria claims up to its quantity_required
            qty_to_claim = min(crit['quantity_required'], len(matching_for_crit))

            if qty_to_claim > 0:
                # Mark items as allocated (FIFO - take first items)
                for i in range(qty_to_claim):
                    item_id = matching_for_crit[i]
                    allocated_ids.add(item_id)
                    item_claims[item_id] = crit['trade_id']

                criteria_claims.append({
                    'trade_id': crit['trade_id'],
                    'criteria_id': crit['id'],
                    'quantity_claimed': qty_to_claim,
                    'registry': crit.get('registry'),
                    'vintage_from': crit.get('vintage_from'),
                    'vintage_to': crit.get('vintage_to')
                })

        claimed_by_criteria = len(allocated_ids)
        available = total_matching - claimed_by_criteria

        # Build inventory list with status
        inventory_items = []
        for item in matching_inventory:
            claiming_trade = item_claims.get(item['id'])
            inventory_items.append({
                'serial': item.get('serial', ''),
                'registry': item.get('registry', ''),
                'product': item.get('product', ''),
                'project_id': item.get('project_id', ''),
                'vintage': item.get('vintage', ''),
                'status': 'claimed' if claiming_trade else 'available',
                'claimed_by_trade': claiming_trade
            })

        return {
            'total_matching': total_matching,
            'claimed_by_criteria': claimed_by_criteria,
            'available': available,
            'criteria_claims': criteria_claims,
            'inventory_items': inventory_items
        }

    except Exception as e:
        if conn:
            conn.close()
        print(f"Error in get_available_after_criteria_claims: {e}")
        return {
            'total_matching': 0,
            'claimed_by_criteria': 0,
            'available': 0,
            'criteria_claims': [],
            'error': str(e)
        }


def get_criteria_allocation_status():
    """
    Optimize and check allocation feasibility for all criteria-only trades.
    Uses a maximum bipartite matching approach to find optimal allocation.

    Returns:
        dict with:
        - 'trade_status': {trade_id: {'status': 'sufficient'|'insufficient'|'conflict',
                                       'available': int, 'required': int, 'shortfall': int}}
        - 'total_available': int
        - 'total_required': int
        - 'conflicts': list of conflicting trade pairs
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get all criteria_only criteria (active sell generic trades)
        cursor.execute("""
            SELECT * FROM trade_criteria
            WHERE status = 'criteria_only' AND direction = 'sell'
            ORDER BY created_at ASC
        """)
        all_criteria = [dict(row) for row in cursor.fetchall()]

        # Get all available inventory (not reserved, not assigned)
        cursor.execute("""
            SELECT id, market, registry, product, project_id, project_type,
                   protocol, vintage, serial
            FROM inventory
            WHERE (is_reserved = 0 OR is_reserved IS NULL)
              AND (is_assigned = 0 OR is_assigned IS NULL)
        """)
        available_inventory = [dict(row) for row in cursor.fetchall()]
        conn.close()
        conn = None  # Mark as closed

        if not all_criteria:
            return {
                'trade_status': {},
                'total_available': len(available_inventory),
                'total_required': 0,
                'conflicts': [],
                'allocation_possible': True
            }

        # Build matching matrix: which inventory items can satisfy which criteria
        # criteria_matches[criteria_id] = [list of inventory item ids that match]
        criteria_matches = {}
        for crit in all_criteria:
            criteria_matches[crit['id']] = []
            for item in available_inventory:
                if check_inventory_matches_criteria(item, crit):
                    criteria_matches[crit['id']].append(item['id'])

        # Track allocated inventory
        allocated = set()
        trade_status = {}
        conflicts = []

        # Track per-criteria status
        criteria_status = {}

        # First pass: Check individual availability (total matching, ignoring other criteria)
        for crit in all_criteria:
            available_for_crit = len(criteria_matches[crit['id']])
            required = crit['quantity_required']
            trade_id = crit['trade_id']
            criteria_id = crit['id']

            criteria_status[criteria_id] = {
                'status': 'sufficient' if available_for_crit >= required else 'insufficient',
                'available': available_for_crit,
                'required': required,
                'shortfall': max(0, required - available_for_crit),
                'trade_id': trade_id,
                'criteria': {
                    'market': crit.get('market'),
                    'registry': crit.get('registry'),
                    'product': crit.get('product'),
                    'project_type': crit.get('project_type'),
                    'protocol': crit.get('protocol'),
                    'project_id': crit.get('project_id'),
                    'vintage_from': crit.get('vintage_from'),
                    'vintage_to': crit.get('vintage_to')
                }
            }

            # Also aggregate at trade level
            if trade_id not in trade_status:
                trade_status[trade_id] = {
                    'status': 'sufficient',
                    'available': 0,
                    'required': 0,
                    'shortfall': 0,
                    'criteria_ids': [],
                    'conflicts_with': []
                }

            trade_status[trade_id]['available'] += available_for_crit
            trade_status[trade_id]['required'] += required
            trade_status[trade_id]['shortfall'] += max(0, required - available_for_crit)
            trade_status[trade_id]['criteria_ids'].append(criteria_id)

            # Update trade status (worst status wins)
            if criteria_status[criteria_id]['status'] == 'insufficient':
                if trade_status[trade_id]['status'] == 'sufficient':
                    trade_status[trade_id]['status'] = 'insufficient'

        # Build id to serial mapping
        id_to_serial = {item['id']: item['serial'] for item in available_inventory}

        # Second pass: Simulate allocation in FIFO order (oldest criteria first)
        # This ensures older trades get priority - newer trades causing conflicts are marked
        # all_criteria is already ordered by created_at ASC from the SQL query
        allocation_success = True
        allocated = set()  # Set of item IDs
        allocated_serials = set()  # Set of serial numbers

        for crit in all_criteria:  # Process in creation order (oldest first)
            trade_id = crit['trade_id']
            criteria_id = crit['id']
            required = crit['quantity_required']

            # Get unallocated items that match this criteria
            available_items = [
                item_id for item_id in criteria_matches[criteria_id]
                if item_id not in allocated
            ]

            if len(available_items) >= required:
                # Allocate required items
                for item_id in available_items[:required]:
                    allocated.add(item_id)
                    if item_id in id_to_serial:
                        allocated_serials.add(id_to_serial[item_id])
                criteria_status[criteria_id]['allocated'] = required
            else:
                # Not enough - mark as conflict
                allocation_success = False
                criteria_status[criteria_id]['status'] = 'conflict'
                criteria_status[criteria_id]['allocated'] = len(available_items)
                criteria_status[criteria_id]['shortfall'] = required - len(available_items)

                # Update trade status to conflict
                trade_status[trade_id]['status'] = 'conflict'

                # Allocate what we can
                for item_id in available_items:
                    allocated.add(item_id)
                    if item_id in id_to_serial:
                        allocated_serials.add(id_to_serial[item_id])

        # Detect specific conflicts (which trades compete for same inventory)
        # Also track which trades each trade conflicts with
        trade_conflicts = {}  # trade_id -> list of conflicting trade_ids

        for i, crit1 in enumerate(all_criteria):
            for crit2 in all_criteria[i+1:]:
                # Check if criteria overlap
                overlap = set(criteria_matches[crit1['id']]) & set(criteria_matches[crit2['id']])
                if overlap:
                    combined_need = crit1['quantity_required'] + crit2['quantity_required']
                    if combined_need > len(overlap):
                        # These criteria compete and may not both be satisfiable
                        conflicts.append({
                            'trade1': crit1['trade_id'],
                            'trade2': crit2['trade_id'],
                            'overlap_count': len(overlap),
                            'combined_need': combined_need
                        })
                        # Track conflicts for each trade
                        if crit1['trade_id'] not in trade_conflicts:
                            trade_conflicts[crit1['trade_id']] = []
                        if crit2['trade_id'] not in trade_conflicts:
                            trade_conflicts[crit2['trade_id']] = []
                        trade_conflicts[crit1['trade_id']].append(crit2['trade_id'])
                        trade_conflicts[crit2['trade_id']].append(crit1['trade_id'])

        # Add conflicting trades to each trade's status
        for trade_id, conflicting_trades in trade_conflicts.items():
            if trade_id in trade_status:
                trade_status[trade_id]['conflicts_with'] = list(set(conflicting_trades))

        total_required = sum(c['quantity_required'] for c in all_criteria)

        return {
            'trade_status': trade_status,
            'criteria_status': criteria_status,
            'total_available': len(available_inventory),
            'total_required': total_required,
            'conflicts': conflicts,
            'allocation_possible': allocation_success,
            'allocated_serials': list(allocated_serials)
        }

    except Exception as e:
        print(f"Error checking criteria allocation: {e}")
        import traceback
        traceback.print_exc()
        return {
            'trade_status': {},
            'total_available': 0,
            'total_required': 0,
            'conflicts': [],
            'allocation_possible': True,
            'error': str(e)
        }
    finally:
        if conn:
            conn.close()


def assign_criteria_only(trade_id, quantity, criteria, username):
    """
    Assign criteria to a trade without reserving specific inventory.
    Records the criteria requirements for later allocation checking.
    Multiple criteria can be assigned to the same trade.

    Args:
        trade_id: the trade ID
        quantity: required quantity
        criteria: dict with filter criteria
        username: user performing the action

    Returns:
        (success, message, criteria_id)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Always insert new criteria (allows multiple criteria per trade)
        cursor.execute("""
            INSERT INTO trade_criteria
            (trade_id, direction, quantity_required, market, registry, product,
             project_type, protocol, project_id, vintage_from, vintage_to, status, created_by)
            VALUES (?, 'sell', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'criteria_only', ?)
        """, (
            str(trade_id),
            quantity,
            criteria.get('market'),
            criteria.get('registry'),
            criteria.get('product'),
            criteria.get('project_type'),
            criteria.get('protocol'),
            criteria.get('project_id'),
            criteria.get('vintage_from'),
            criteria.get('vintage_to'),
            username
        ))
        criteria_id = cursor.lastrowid

        # Count how many criteria this trade now has
        cursor.execute("""
            SELECT COUNT(*) as count FROM trade_criteria
            WHERE trade_id = ? AND direction = 'sell' AND status = 'criteria_only'
        """, (str(trade_id),))
        count = cursor.fetchone()['count']

        message = f"Added criteria #{count} to trade {trade_id}"

        conn.commit()
        return True, message, criteria_id

    except Exception as e:
        print(f"Error assigning criteria: {e}")
        return False, str(e), None
    finally:
        if conn:
            conn.close()


def get_trade_criteria_summary():
    """
    Get summary of all trades with criteria_only status.

    Returns:
        Dict mapping trade_id to list of criteria details
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trade_criteria
            WHERE status = 'criteria_only'
            ORDER BY trade_id, created_at
        """)
        rows = cursor.fetchall()

        result = {}
        for row in rows:
            trade_id = row['trade_id']
            criteria = {
                'criteria_id': row['id'],
                'quantity': row['quantity_required'],
                'quantity_required': row['quantity_required'],
                'direction': row['direction'],
                'market': row['market'],
                'registry': row['registry'],
                'product': row['product'],
                'project_type': row['project_type'],
                'protocol': row['protocol'],
                'project_id': row['project_id'],
                'vintage_from': row['vintage_from'],
                'vintage_to': row['vintage_to'],
                'created_at': row['created_at']
            }
            if trade_id not in result:
                result[trade_id] = []
            result[trade_id].append(criteria)

        return result

    except Exception as e:
        print(f"Error getting trade criteria summary: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def remove_trade_criteria(trade_id, username):
    """
    Remove criteria_only assignment from a trade.

    Args:
        trade_id: the trade ID
        username: user performing the action

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM trade_criteria
            WHERE trade_id = ? AND status = 'criteria_only'
        """, (str(trade_id),))

        deleted = cursor.rowcount
        conn.commit()

        if deleted > 0:
            return True, f"Removed criteria from trade {trade_id}"
        else:
            return False, "No criteria found for this trade"

    except Exception as e:
        print(f"Error removing trade criteria: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def remove_single_criteria(criteria_id, username):
    """
    Remove a single criteria by its ID.

    Args:
        criteria_id: the criteria ID
        username: user performing the action

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM trade_criteria
            WHERE id = ? AND status = 'criteria_only'
        """, (criteria_id,))

        deleted = cursor.rowcount
        conn.commit()

        if deleted > 0:
            return True, f"Removed criteria {criteria_id}"
        else:
            return False, "Criteria not found"

    except Exception as e:
        print(f"Error removing criteria: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def update_single_criteria(criteria_id, quantity, criteria, username):
    """
    Update a single criteria's fields.

    Args:
        criteria_id: the criteria ID to update
        quantity: new quantity
        criteria: dict with filter criteria fields
        username: user performing the action

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE trade_criteria SET
                quantity_required = ?,
                registry = ?,
                product = ?,
                project_type = ?,
                protocol = ?,
                project_id = ?,
                vintage_from = ?,
                vintage_to = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'criteria_only'
        """, (
            quantity,
            criteria.get('registry'),
            criteria.get('product'),
            criteria.get('project_type'),
            criteria.get('protocol'),
            criteria.get('project_id'),
            criteria.get('vintage_from'),
            criteria.get('vintage_to'),
            criteria_id
        ))

        updated = cursor.rowcount
        conn.commit()

        if updated > 0:
            return True, f"Updated criteria {criteria_id}"
        else:
            return False, "Criteria not found"

    except Exception as e:
        print(f"Error updating criteria: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def update_criteria_quantity(trade_id, delta, username):
    """
    Update criteria quantities for a trade when inventory is assigned/unassigned.

    When delta is negative (assigning inventory), reduces from first criteria with remaining quantity.
    When delta is positive (unassigning inventory), adds to first criteria.
    If a criteria quantity reaches 0, it is removed.

    Args:
        trade_id: the trade ID
        delta: amount to add (positive) or subtract (negative)
        username: user performing the action

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get all criteria for this trade ordered by ID (FIFO)
        cursor.execute("""
            SELECT id, quantity_required FROM trade_criteria
            WHERE trade_id = ? AND direction = 'sell' AND status = 'criteria_only'
            ORDER BY id ASC
        """, (str(trade_id),))
        criteria_list = cursor.fetchall()

        if not criteria_list:
            return True, "No criteria to update"

        remaining_delta = delta

        if delta < 0:
            # Reducing quantity (assigning inventory)
            amount_to_reduce = abs(delta)
            for crit in criteria_list:
                if amount_to_reduce <= 0:
                    break
                crit_id = crit['id']
                crit_qty = crit['quantity_required'] or 0

                if crit_qty > 0:
                    reduce_by = min(crit_qty, amount_to_reduce)
                    new_qty = crit_qty - reduce_by
                    amount_to_reduce -= reduce_by

                    if new_qty <= 0:
                        # Remove criteria if quantity reaches 0
                        cursor.execute("DELETE FROM trade_criteria WHERE id = ?", (crit_id,))
                    else:
                        cursor.execute("""
                            UPDATE trade_criteria SET quantity_required = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (new_qty, crit_id))
        else:
            # Increasing quantity (unassigning inventory)
            # Add to the first criteria, or create new one if none exist
            if criteria_list:
                first_crit = criteria_list[0]
                new_qty = (first_crit['quantity_required'] or 0) + delta
                cursor.execute("""
                    UPDATE trade_criteria SET quantity_required = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_qty, first_crit['id']))

        conn.commit()
        return True, f"Updated criteria quantities for trade {trade_id}"

    except Exception as e:
        print(f"Error updating criteria quantity: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def update_specific_criteria_quantity(criteria_id, delta, username):
    """
    Update a specific criteria's quantity when inventory is assigned/unassigned.

    Args:
        criteria_id: the specific criteria ID to update
        delta: amount to add (positive) or subtract (negative)
        username: user performing the action

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Get the specific criteria
        cursor.execute("""
            SELECT id, quantity_required, trade_id FROM trade_criteria
            WHERE id = ? AND status = 'criteria_only'
        """, (criteria_id,))
        criteria = cursor.fetchone()

        if not criteria:
            return True, "Criteria not found or not active"

        crit_qty = criteria['quantity_required'] or 0
        new_qty = crit_qty + delta

        if new_qty <= 0:
            # Remove criteria if quantity reaches 0
            cursor.execute("DELETE FROM trade_criteria WHERE id = ?", (criteria_id,))
        else:
            cursor.execute("""
                UPDATE trade_criteria SET quantity_required = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_qty, criteria_id))

        conn.commit()
        return True, f"Updated criteria {criteria_id} quantity"

    except Exception as e:
        print(f"Error updating specific criteria quantity: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def get_trade_criteria_ids(trade_id):
    """
    Get all criteria IDs for a trade.

    Args:
        trade_id: the trade ID

    Returns:
        list of criteria IDs
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM trade_criteria
            WHERE trade_id = ? AND direction = 'sell' AND status = 'criteria_only'
            ORDER BY id ASC
        """, (str(trade_id),))

        return [row['id'] for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error getting criteria IDs: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_criteria_by_id(criteria_id):
    """
    Get criteria details by ID.

    Args:
        criteria_id: the criteria ID

    Returns:
        dict with criteria details or None if not found
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, trade_id, direction, quantity_required, quantity_fulfilled,
                   market, registry, product, project_type, protocol, project_id,
                   vintage_from, vintage_to, status, created_by, created_at, updated_at
            FROM trade_criteria
            WHERE id = ?
        """, (criteria_id,))

        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    except Exception as e:
        print(f"Error getting criteria by ID: {e}")
        return None
    finally:
        if conn:
            conn.close()


def restore_criteria_on_unassign(criteria_id, quantity, username, criteria_snapshot=None):
    """
    Restore criteria quantity when inventory is unassigned.
    If the criteria was deleted, recreate it with the saved attributes.

    Args:
        criteria_id: the criteria ID that was used when assigning
        quantity: number of items being unassigned
        username: user performing the action
        criteria_snapshot: optional dict with criteria attributes to restore if deleted

    Returns:
        (success, message)
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # Check if criteria still exists
        cursor.execute("""
            SELECT id, quantity_required, trade_id, direction, market, registry, product,
                   project_type, protocol, project_id, vintage_from, vintage_to, status, created_by
            FROM trade_criteria
            WHERE id = ?
        """, (criteria_id,))
        criteria = cursor.fetchone()

        if criteria:
            # Criteria exists - add quantity back
            new_qty = (criteria['quantity_required'] or 0) + quantity
            cursor.execute("""
                UPDATE trade_criteria SET quantity_required = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_qty, criteria_id))
            conn.commit()
            return True, f"Restored {quantity} to existing criteria {criteria_id}"
        elif criteria_snapshot:
            # Criteria was deleted - recreate it with saved attributes
            cursor.execute("""
                INSERT INTO trade_criteria (
                    trade_id, direction, quantity_required, quantity_fulfilled,
                    market, registry, product, project_type, protocol, project_id,
                    vintage_from, vintage_to, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'criteria_only', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                criteria_snapshot.get('trade_id'),
                criteria_snapshot.get('direction', 'sell'),
                quantity,
                criteria_snapshot.get('market'),
                criteria_snapshot.get('registry'),
                criteria_snapshot.get('product'),
                criteria_snapshot.get('project_type'),
                criteria_snapshot.get('protocol'),
                criteria_snapshot.get('project_id'),
                criteria_snapshot.get('vintage_from'),
                criteria_snapshot.get('vintage_to'),
                username
            ))
            new_criteria_id = cursor.lastrowid
            conn.commit()
            return True, f"Recreated criteria with {quantity} items (new ID: {new_criteria_id})"
        else:
            return False, "Criteria not found and no snapshot to recreate"

    except Exception as e:
        print(f"Error restoring criteria on unassign: {e}")
        return False, str(e)
    finally:
        if conn:
            conn.close()


def get_inventory_criteria_info(serials):
    """
    Get criteria information for inventory items by their serials.
    Returns a dict mapping serial to criteria snapshot.

    Args:
        serials: list of serial numbers

    Returns:
        dict: {serial: {'criteria_id': id, 'criteria_snapshot': {...}}}
    """
    conn = None
    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        result = {}
        for serial in serials:
            # Get the criteria_id and stored snapshot from inventory
            cursor.execute("""
                SELECT criteria_id, trade_id, criteria_snapshot FROM inventory WHERE serial = ?
            """, (serial,))
            inv = cursor.fetchone()

            if inv and inv['criteria_id']:
                criteria_id = inv['criteria_id']
                stored_snapshot = inv['criteria_snapshot']

                # Get the criteria details (may be None if deleted)
                cursor.execute("""
                    SELECT id, trade_id, direction, quantity_required, market, registry, product,
                           project_type, protocol, project_id, vintage_from, vintage_to, status
                    FROM trade_criteria
                    WHERE id = ?
                """, (criteria_id,))
                crit = cursor.fetchone()

                if crit:
                    result[serial] = {
                        'criteria_id': criteria_id,
                        'criteria_snapshot': dict(crit)
                    }
                elif stored_snapshot:
                    # Criteria was deleted - use the stored snapshot
                    try:
                        snapshot_dict = json.loads(stored_snapshot)
                        result[serial] = {
                            'criteria_id': criteria_id,
                            'criteria_snapshot': snapshot_dict
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass

        return result

    except Exception as e:
        print(f"Error getting inventory criteria info: {e}")
        return {}
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    init_database()
    init_inventory_database()
