# Quick Start Guide - Carbon IMS

## For Windows Users

### One-Time Setup
1. Double-click `setup.bat`
2. Wait for setup to complete (installs dependencies and creates databases)

### Running the Application
1. Double-click `start.bat`
2. Open browser: http://127.0.0.1:5000
3. Login: `admin` / `admin123`
4. Change password immediately in Settings

### Stopping the Application
- Press `Ctrl+C` in the command window
- Or close the command window

---

## For Mac/Linux Users

### One-Time Setup
```bash
chmod +x setup.sh start.sh
./setup.sh
```

### Running the Application
```bash
./start.sh
```
Then open browser: http://127.0.0.1:5000

### Stopping the Application
- Press `Ctrl+C` in the terminal

---

## Default Login Credentials

**Username:** admin
**Password:** admin123

⚠️ **IMPORTANT:** Change this password immediately after first login!

---

## First Steps After Login

1. **Change Admin Password**
   - Click username → Settings
   - Enter current password: `admin123`
   - Enter new password (twice)
   - Click "Save Changes"

2. **Create Users** (Admin only)
   - Go to "User Management"
   - Click "+ Add User"
   - Fill in details and select role:
     - **Admin**: Full access
     - **Trader**: Can edit inventory/warranties
     - **Ops**: Read-only access

3. **Add Inventory**
   - Go to "Inventory Management"
   - Click "Add New Item"
   - Fill in item details
   - Click "Add Item"

4. **Assign Warranties**
   - Go to "Warranties"
   - Click "Assign Warranty"
   - Enter serial number or range
   - Fill in warranty details
   - Preview and confirm

---

## Common Tasks

### Import Existing Data
- Contact administrator for bulk import scripts
- Or use "Add New Item" to enter manually

### Export Data
- Use browser's print function (Ctrl+P)
- Select "Save as PDF"
- Or use backup/restore feature for database export

### View Backups (Admin Only)
- Go to Inventory or Warranties page
- Click "View Backups"
- Browse by date
- Click "Restore" to rollback changes

### Search and Filter
- Use filter boxes at top of each column
- Supports wildcards:
  - `*` = any characters
  - `?` = single character
- Click column headers to sort

---

## Troubleshooting

### Can't Access Application
- Check if app is running (command window open)
- Verify URL: http://127.0.0.1:5000 (not https)
- Try different browser

### Login Issues
- Username/password are case-sensitive
- Default is `admin` / `admin123`
- If locked out, run `setup.bat` again to reset

### Port Already in Use
- Another application is using port 5000
- Stop the other application
- Or modify `app.py` to use different port

### Changes Not Saving (Trader/Admin)
- Click "Save Changes" button after editing
- Check role permissions (Ops can't edit)

---

## Getting Help

1. Check README.md for detailed documentation
2. Review error messages in browser console (F12)
3. Check command window for server errors

---

## System Requirements

- **Python**: 3.8 or higher
- **RAM**: 512MB minimum
- **Disk**: 100MB free space
- **Browser**: Chrome, Firefox, Edge, or Safari (latest version)
- **OS**: Windows 10+, macOS 10.14+, or Linux

---

## Security Notes

✓ Always use strong passwords
✓ Change default admin password
✓ Limit admin accounts to authorized personnel
✓ Regular backups recommended
✓ Application runs locally only (not exposed to internet)

---

**Version 1.0** | Created by Mike Cheung | December 2025
