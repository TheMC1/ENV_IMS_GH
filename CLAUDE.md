# Carbon IMS - Claude Context File

## Project Overview
Carbon IMS (Inventory Management System) is a Flask-based web application for managing carbon credit inventory, warranties, and trades. It features user authentication, role-based access control, activity logging, and backup/restore functionality.

## Technology Stack
- **Backend**: Python 3, Flask
- **Database**: SQLite (users.db for auth/logs, inventory.db for inventory data)
- **Frontend**: HTML, CSS, JavaScript (vanilla)
- **Authentication**: Flask sessions with password hashing (werkzeug)

## Project Structure
```
IMS/
├── app.py                 # Main Flask application entry point
├── database.py            # All database functions (users, inventory, logs)
├── trades_data.py         # External trades data source configuration
├── routes/
│   ├── __init__.py        # Blueprint exports
│   ├── auth.py            # Authentication routes and decorators
│   ├── inventory.py       # Inventory CRUD operations
│   ├── warranties.py      # Warranty management
│   ├── trades.py          # Trade assignment operations
│   ├── logs.py            # Activity logs with undo/redo
│   ├── dashboard.py       # Dashboard analytics
│   ├── reports.py         # Report generation
│   ├── settings.py        # User settings
│   ├── users.py           # User management (admin)
│   └── registry.py        # External registry queries
├── templates/
│   ├── login.html         # Login page
│   ├── home.html          # Home dashboard with navigation cards
│   ├── inventory.html     # Inventory management (main data grid)
│   ├── warranties.html    # Warranty management
│   ├── trades.html        # Trade assignment interface
│   ├── logs.html          # Activity logs viewer
│   ├── dashboard.html     # Analytics dashboard
│   ├── reports.html       # Reports page
│   ├── settings.html      # User settings
│   └── users.html         # User management (admin)
├── static/
│   ├── style.css          # Main stylesheet
│   └── bg-forest.jpg      # Background image
├── backups/               # Inventory backup files (JSON)
└── data/                  # Data files directory
```

## Databases

### users.db (Main Database)
- `users` - User accounts with roles and preferences
- `role_permissions` - Page access permissions per role
- `user_page_settings` - User-specific page settings (filters, etc.)
- `activity_logs` - All system activity for audit trail

### inventory.db (Inventory Database)
- `inventory` - Carbon credit inventory items
- `warranties` - Warranty information linked to inventory by serial

## Key Concepts

### User Roles
- **admin**: Full access, can manage users, undo/redo actions
- **trader**: Read/write access to inventory and trades
- **ops**: Read-only access

### Authentication Decorators (routes/auth.py)
```python
@login_required          # Requires authenticated user
@admin_required          # Requires admin role
@write_access_required   # Requires admin or trader role
@page_access_required('page_id')  # Checks role_permissions table
```

### Activity Logging
All data modifications should be logged using:
```python
from database import log_activity

log_activity(
    username=username,
    action_type='add|update|delete|import|assign|unassign',
    target_type='inventory|warranty|trade',
    target_id=str(id),
    serial=serial_number,
    details='Human readable description',
    before_data=dict_before,  # For update/delete
    after_data=dict_after     # For add/update
)
```

### Undo/Redo System
- Undo reverts an action using `before_data`
- Redo re-applies an action using `after_data`
- Uses `mark_activity_reverted()` and `clear_activity_reverted()`
- Only works for inventory and warranty actions

## Common Patterns

### Adding a New Route
1. Create route file in `routes/` folder
2. Create Blueprint: `my_bp = Blueprint('my', __name__)`
3. Add routes with appropriate decorators
4. Export in `routes/__init__.py`
5. Register in `app.py`: `app.register_blueprint(my_bp)`

### Adding Activity Logging to a Route
```python
from database import log_activity

# Get before_data if updating/deleting
items = get_all_items()
before_item = next((i for i in items if i.get('id') == target_id), None)

# Perform the operation
success, result = do_operation(data)

if success:
    log_activity(
        username=session.get('user'),
        action_type='update',
        target_type='inventory',
        target_id=str(target_id),
        serial=data.get('Serial', ''),
        details=f'Updated item: Serial {serial}',
        before_data=dict(before_item) if before_item else None,
        after_data=data
    )
```

### Frontend Data Tables
Tables use a common pattern:
- Load data via `/api/{resource}/get`
- Track modifications in `pendingModifications` object
- Commit changes via `/api/{resource}/commit-batch`
- Changes are logged in batch commit

### Backup System
- Backups stored in `backups/` as timestamped JSON files
- Include inventory + warranty data
- Created on: add, update, delete, import, batch commit
- Restore available in inventory settings modal

## trades_data.py Configuration
Controls which columns display in trades table:
```python
DISPLAY_COLUMNS = ['DealNumber', 'Counterparty', 'Notional', ...]  # Set to None for all columns
```

## Key Database Functions (database.py)

### Inventory
- `get_all_inventory_items()` - Returns list of dicts with `_row_index`
- `add_inventory_item(data)` - Returns (success, id)
- `update_inventory_item(row_index, data)` - Returns (success, message)
- `delete_inventory_item(row_index)` - Returns (success, message)

### Activity Logs
- `log_activity(...)` - Create log entry
- `get_activity_logs(filters, limit, offset)` - Query logs
- `get_activity_log_by_id(id)` - Get single log with parsed JSON
- `mark_activity_reverted(log_id, username)` - Mark as undone
- `clear_activity_reverted(log_id)` - Clear undone status (for redo)

### Backups
- `create_inventory_backup(username, description, changes_summary)`
- `restore_inventory_backup(backup_id)` - Restores inventory + warranties

## Recent Features Added

### Activity Logs Page (logs.html, routes/logs.py)
- Displays all system activity
- Filter by user, action, target, serial, date, status
- Groups sequential operations (same user/action/target within 60 seconds)
- Undo button for active items (admin only)
- Redo button for undone items (admin only)
- Expandable groups with "Undo All" / "Redo All"

### Batch Commit Logging
Inventory batch commits now log each individual change:
- Modifications logged with before_data and after_data
- Deletions logged with before_data
- Additions logged with after_data

## Environment
- Windows 10/11
- Python virtual environment in `.venv/`
- Run with: `.venv\Scripts\python.exe app.py`
- Default port: 5000

## Testing Changes
```bash
# Verify imports work
.venv\Scripts\python.exe -c "from app import app; print('OK')"

# Check route count
.venv\Scripts\python.exe -c "from app import app; print(len(list(app.url_map.iter_rules())))"
```
