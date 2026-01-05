# Carbon IMS - Claude Context File

## Project Overview
Carbon IMS (Inventory Management System) is a Flask-based web application for managing carbon credit inventory, warranties, and trades. It features user authentication, role-based access control, activity logging, trade criteria management, generic allocation, and backup/restore functionality.

## Technology Stack
- **Backend**: Python 3, Flask
- **Database**: SQLite (ims_users.db for auth/logs, ims_inventory.db for inventory/trades data)
- **Frontend**: HTML, CSS, JavaScript (vanilla)
- **Authentication**: Flask sessions with password hashing (werkzeug)

## Project Structure
```
IMS/
├── app.py                 # Main Flask application entry point
├── database.py            # All database functions (users, inventory, trades, logs)
├── trades_data.py         # External trades data source configuration
├── routes/
│   ├── __init__.py        # Blueprint exports
│   ├── auth.py            # Authentication routes and decorators
│   ├── inventory.py       # Inventory CRUD operations
│   ├── warranties.py      # Warranty management
│   ├── trades.py          # Trade assignment, criteria, reservations
│   ├── logs.py            # Activity logs with undo/redo
│   ├── dashboard.py       # Dashboard analytics
│   ├── reports.py         # Report generation
│   ├── settings.py        # User settings
│   ├── users.py           # User management (admin)
│   ├── backups.py         # Backup management
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
│   ├── users.html         # User management (admin)
│   └── registry_data.html # Registry data viewer
├── static/
│   ├── style.css          # Main stylesheet
│   └── bg-forest.jpg      # Background image
├── backups/               # Inventory backup files (JSON)
└── data/                  # Data files directory
```

## Databases

### ims_users.db (Main Database)
- `users` - User accounts with roles and preferences
- `role_permissions` - Page access permissions per role
- `user_settings` - User-specific page settings (filters, etc.)
- `activity_logs` - All system activity for audit trail

### ims_inventory.db (Inventory Database)
- `inventory` - Carbon credit inventory items
  - Columns: id, market, registry, product, project_id, project_type, protocol, project_name, vintage, serial, is_custody, is_assigned, trade_id, criteria_id, criteria_snapshot
- `warranties` - Warranty information linked to inventory by serial
- `inventory_backups` - Backup snapshots
- `trade_criteria` - Trade criteria for generic allocation
  - Columns: id, trade_id, direction, quantity_required, quantity_fulfilled, market, registry, product, project_type, protocol, project_id, vintage_from, vintage_to, status, created_by
- `inventory_reservations` - Reservation history
- `generic_inventory` - Generic inventory items

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

### Trade Criteria System
Trade criteria allows "Generic Allocation" - reserving inventory by criteria without specifying exact serials:
- Create criteria with: registry, product, project_type, protocol, project_id, vintage_from, vintage_to, quantity
- Status: 'criteria_only' for generic allocation
- FIFO ordering: First criteria created gets priority for matching inventory
- When inventory is assigned via criteria, `criteria_id` and `criteria_snapshot` are stored
- When unassigned, criteria quantity is restored (or recreated if deleted)

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

## Key Database Functions (database.py)

### Inventory
- `get_all_inventory_items()` - Returns list of dicts with `_row_index`
- `add_inventory_item(data)` - Returns (success, id)
- `update_inventory_item(row_index, data)` - Returns (success, message)
- `delete_inventory_item(row_index)` - Returns (success, message)
- `get_unassigned_inventory()` - Get items not assigned to trades

### Trade Assignment
- `assign_inventory_to_trade(serials, trade_id, warranty_data, criteria_id)` - Assign with optional criteria tracking
- `unassign_inventory_from_trade(serials, username, restore_criteria)` - Unassign and restore criteria
- `get_inventory_by_trade(trade_id)` - Get items for a trade

### Trade Criteria
- `create_trade_criteria(...)` - Create new criteria
- `get_trade_criteria(trade_id)` - Get criteria for a trade
- `update_criteria_quantity(trade_id, delta, username)` - FIFO quantity update
- `update_specific_criteria_quantity(criteria_id, delta, username)` - Specific criteria update
- `restore_criteria_on_unassign(criteria_id, quantity, username, snapshot)` - Restore/recreate criteria
- `get_available_after_criteria_claims(criteria)` - Check availability considering claims

### Activity Logs
- `log_activity(...)` - Create log entry
- `get_activity_logs(filters, limit, offset)` - Query logs
- `get_activity_log_by_id(id)` - Get single log with parsed JSON
- `mark_activity_reverted(log_id, username)` - Mark as undone

### Backups
- `create_inventory_backup(username, description, changes_summary)`
- `restore_inventory_backup(backup_id)` - Restores inventory + warranties

## trades_data.py Configuration
Controls which columns display in trades table:
```python
DISPLAY_COLUMNS = ['DealNumber', 'Counterparty', 'Notional', ...]  # Set to None for all columns
```

## Recent Features

### Trade Criteria & Generic Allocation
- Create "criteria only" reservations on sell trades
- Criteria match inventory by: registry, product, vintage range, project_id, etc.
- FIFO ordering determines claim priority
- Quantity automatically restored when inventory unassigned

### Locate Inventory Modal
- Search for matching inventory with criteria
- Shows availability status (Available/Claimed)
- Accounts for generic allocation claims
- Groups consecutive serials

### Criteria-Specific Assignment Tracking
- When assigning via criteria's "+" button, stores criteria_id and snapshot
- On unassign, restores exact criteria (or recreates if deleted)
- Ensures criteria parameters preserved for recreation

### Draggable Modals
- All modals are draggable by header
- Resets position when closed/reopened

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
