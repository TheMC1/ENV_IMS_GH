# Carbon IMS - Inventory Management System

A Flask-based web application for managing carbon credit inventory and warranties.

## Features

- **User Management**: Admin, Trader, and Ops roles with different permission levels
- **Inventory Management**: Track carbon credits with full CRUD operations
- **Warranties Management**: Manage warranty assignments linked to inventory
- **Backup & Restore**: Automated backup system with point-in-time restore
- **Advanced Filtering**: Search, sort, and filter with pagination
- **Role-Based Access Control**:
  - Admin: Full access including user management and backups
  - Trader: Can modify inventory and warranties
  - Ops: Read-only access to all data
- **User Preferences**: Customizable view settings per user

## System Requirements

- Python 3.8 or higher
- Windows, macOS, or Linux
- Modern web browser (Chrome, Firefox, Edge, Safari)

## Installation Instructions

### Step 1: Install Python

1. Download Python from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Verify installation:
   ```bash
   python --version
   ```
   or
   ```bash
   py --version
   ```

### Step 2: Extract Application Files

1. Copy the entire `IMS` folder to your desired location
2. Navigate to the folder:
   ```bash
   cd path/to/IMS
   ```

### Step 3: Create Virtual Environment

**Windows:**
```bash
py -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Initialize Databases

**Windows:**
```bash
py -c "from database import init_database, init_inventory_database; init_database(); init_inventory_database()"
```

**macOS/Linux:**
```bash
python -c "from database import init_database, init_inventory_database; init_database(); init_inventory_database()"
```

This will create:
- `ims_users.db` - User database with default admin account
- `ims_inventory.db` - Inventory and warranties database

### Step 6: Run the Application

**Windows:**
```bash
py app.py
```

**macOS/Linux:**
```bash
python app.py
```

The application will start on `http://127.0.0.1:5000`

### Step 7: First Login

1. Open your browser and navigate to `http://127.0.0.1:5000`
2. Login with default credentials:
   - **Username:** `admin`
   - **Password:** `admin123`
3. **IMPORTANT:** Change the admin password immediately:
   - Click on username dropdown → Settings
   - Enter new password
   - Save changes

## Quick Start Guide

### Creating Users

1. Login as admin
2. Navigate to "User Management"
3. Click "Add User"
4. Fill in user details and select role:
   - **Admin**: Full system access
   - **Trader**: Can edit inventory and warranties
   - **Ops**: Read-only access
5. Click "Create User"

### Managing Inventory

1. Navigate to "Inventory Management"
2. Use filters to search for specific items
3. Click "Add New Item" to add inventory
4. Click on cells to edit (if you have permission)
5. Click "Save Changes" to commit edits
6. Use "Advanced Sort" for multi-level sorting
7. Use "Bulk Delete" to remove multiple items

### Managing Warranties

1. Navigate to "Warranties"
2. Click "Assign Warranty" to create warranty assignments
3. Enter serial number(s) or range (e.g., "ABC-001:ABC-010")
4. Fill in warranty details
5. Preview and confirm assignments

### Backup & Restore (Admin Only)

1. Navigate to Inventory or Warranties page
2. Click "View Backups"
3. Backups are automatically created after each change
4. Click "Restore" to rollback to a previous state
5. Click "Summary" to view change details
6. Click "Delete" to remove old backups

## Project Structure

```
IMS/
├── app.py                  # Main Flask application
├── database.py             # Database functions and models
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css          # Application styles
├── templates/
│   ├── login.html         # Login page
│   ├── home.html          # Dashboard
│   ├── inventory.html     # Inventory management
│   ├── warranties.html    # Warranty management
│   ├── users.html         # User management
│   └── settings.html      # User settings
├── ims_users.db           # User database (created on init)
├── ims_inventory.db       # Inventory database (created on init)
└── archive/               # Archived migration and test scripts
```

## Database Schema

### Users Table
- username, password (hashed), role, permissions
- first_name, last_name, email, display_name
- view preferences (view_mode, custody_view, rows_per_page)
- warranty preferences (warranty_view_mode, warranty_custody_view, warranty_rows_per_page)

### Inventory Table
- market, registry, product, project_id, project_type
- protocol, project_name, serial, is_custody

### Warranties Table
- serial (links to inventory)
- warranty_start, warranty_end
- opl_tradeid, client, side

### Backups Table
- username, action, summary, backup_data (JSON)
- created_at (EST timezone)

## User Roles & Permissions

| Feature | Admin | Trader | Ops |
|---------|-------|--------|-----|
| View Inventory | ✓ | ✓ | ✓ |
| Edit Inventory | ✓ | ✓ | ✗ |
| View Warranties | ✓ | ✓ | ✓ |
| Edit Warranties | ✓ | ✓ | ✗ |
| User Management | ✓ | ✗ | ✗ |
| Backup/Restore | ✓ | ✗ | ✗ |
| View Backups | ✓ | ✗ | ✗ |

## Troubleshooting

### Port Already in Use
If port 5000 is already in use, modify `app.py` line 851:
```python
app.run(debug=True, host='127.0.0.1', port=5001)
```

### Database Locked Error
- Ensure only one instance of the application is running
- Close any database browsers/tools accessing the .db files

### Permission Denied
- Ensure you have write permissions in the application directory
- Run from a location where you have full access (not Program Files)

### Module Not Found
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

### Login Issues
- Reset admin password by deleting `ims_users.db` and running Step 5 again
- This will recreate the database with default credentials

## Security Notes

1. **Change Default Password**: Always change the admin password after first login
2. **Network Access**: By default, the app only listens on localhost (127.0.0.1)
3. **Production Use**: This is configured for local development/testing
4. **Password Storage**: Passwords are hashed using Werkzeug's security functions
5. **Session Management**: Sessions use Flask's secure session cookies

## Backup Recommendations

1. Regularly backup the database files (`ims_users.db` and `ims_inventory.db`)
2. Store backups in a separate location
3. Use the built-in backup system for inventory changes
4. Export important data periodically

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review browser console for error messages (F12)
3. Check Flask console output for server errors

## Version Information

- **Version**: 1.0
- **Created By**: Mike Cheung
- **Last Updated**: December 2025

## License

Internal use only - Carbon IMS Application
