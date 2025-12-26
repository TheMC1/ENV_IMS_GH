# Deployment Checklist

Use this checklist when deploying Carbon IMS to a new computer.

## Pre-Deployment

- [ ] Python 3.8+ installed on target computer
- [ ] Target computer has internet access (for pip install)
- [ ] Administrator/installation privileges available
- [ ] At least 100MB free disk space

## Files to Copy

Copy the entire `IMS` folder containing:

### Required Files
- [ ] `app.py` - Main application
- [ ] `database.py` - Database functions
- [ ] `requirements.txt` - Dependencies
- [ ] `init_databases.py` - Database initialization
- [ ] `setup.bat` / `setup.sh` - Setup scripts
- [ ] `start.bat` / `start.sh` - Startup scripts
- [ ] `README.md` - Full documentation
- [ ] `QUICK_START.md` - Quick reference
- [ ] `.gitignore` - Git configuration

### Required Folders
- [ ] `static/` - Contains style.css
- [ ] `templates/` - All HTML templates

### Optional (Do NOT Copy)
- [ ] ~~`.venv/`~~ - Will be created during setup
- [ ] ~~`__pycache__/`~~ - Will be created automatically
- [ ] ~~`.claude/`~~ - Development only
- [ ] ~~`.idea/`~~ - IDE settings
- [ ] ~~`ims_users.db`~~ - Will be created (unless migrating users)
- [ ] ~~`ims_inventory.db`~~ - Will be created (unless migrating data)
- [ ] ~~`archive/`~~ - Optional backup scripts

## Installation Steps

### Windows
1. [ ] Copy `IMS` folder to destination
2. [ ] Right-click `setup.bat` → Run as Administrator
3. [ ] Wait for setup to complete
4. [ ] Verify no error messages
5. [ ] Run `start.bat` to test

### Mac/Linux
1. [ ] Copy `IMS` folder to destination
2. [ ] Open Terminal in IMS folder
3. [ ] Run: `chmod +x setup.sh start.sh`
4. [ ] Run: `./setup.sh`
5. [ ] Verify no error messages
6. [ ] Run: `./start.sh` to test

## Post-Installation Verification

### Test Login
- [ ] Open browser: http://127.0.0.1:5000
- [ ] Login page loads correctly
- [ ] Can login with admin/admin123
- [ ] Dashboard displays properly

### Test Navigation
- [ ] "Inventory Management" page loads
- [ ] "Warranties" page loads
- [ ] "User Management" page loads (admin only)
- [ ] "Settings" page loads

### Test Basic Functions
- [ ] Can view inventory data
- [ ] Can add new inventory item (trader/admin)
- [ ] Can edit inventory item (trader/admin)
- [ ] Can save changes (trader/admin)
- [ ] Can view warranties
- [ ] Can assign warranty (trader/admin)

### Security Setup
- [ ] Change admin password immediately
- [ ] Create test user account
- [ ] Test user permissions work correctly
- [ ] Verify ops users are read-only

## Data Migration (Optional)

If migrating from another installation:

### Migrate Users
1. [ ] Copy `ims_users.db` from old installation
2. [ ] Place in new IMS folder
3. [ ] Skip database initialization for users
4. [ ] Test login with existing accounts

### Migrate Inventory
1. [ ] Copy `ims_inventory.db` from old installation
2. [ ] Place in new IMS folder
3. [ ] Skip database initialization for inventory
4. [ ] Verify data appears correctly

### Migrate Both
1. [ ] Copy both .db files from old installation
2. [ ] Place in new IMS folder
3. [ ] Run application with `start.bat` or `start.sh`
4. [ ] Verify all data and users present

## Troubleshooting

### Setup Fails
- [ ] Check Python version: `python --version`
- [ ] Check internet connection
- [ ] Review error messages in terminal
- [ ] Try running with administrator privileges

### Application Won't Start
- [ ] Verify virtual environment exists: `.venv` folder
- [ ] Check if port 5000 is available
- [ ] Review console output for errors
- [ ] Check database files were created

### Can't Login
- [ ] Verify databases exist (ims_users.db)
- [ ] Check credentials: admin/admin123
- [ ] Try deleting ims_users.db and re-running setup

### No Data Showing
- [ ] Check browser console (F12) for errors
- [ ] Verify ims_inventory.db exists
- [ ] Check user role (ops users see read-only)
- [ ] Try adding a test item

## Support Contacts

**Technical Issues:**
- Check README.md Troubleshooting section
- Review error messages in browser console
- Check Flask server console output

**Data Issues:**
- Verify database files present
- Check file permissions
- Review backup/restore options

## Deployment Complete

- [ ] All tests passed
- [ ] Admin password changed
- [ ] Test users created
- [ ] Documentation provided to users
- [ ] Backup procedure established

---

**Deployment Date:** _____________

**Deployed By:** _____________

**System:** Windows / Mac / Linux

**Python Version:** _____________

**Notes:**
_____________________________________________
_____________________________________________
_____________________________________________

