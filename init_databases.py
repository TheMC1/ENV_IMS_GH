#!/usr/bin/env python3
"""
Database Initialization Script
Run this script to create and initialize the database files.
"""

from database import init_database, init_inventory_database

def main():
    print("=" * 60)
    print("Carbon IMS - Database Initialization")
    print("=" * 60)
    print()

    print("Initializing user database...")
    try:
        init_database()
        print("✓ User database (ims_users.db) created successfully")
        print("  Default admin credentials:")
        print("    Username: admin")
        print("    Password: admin123")
        print()
    except Exception as e:
        print(f"✗ Error creating user database: {e}")
        return False

    print("Initializing inventory database...")
    try:
        init_inventory_database()
        print("✓ Inventory database (ims_inventory.db) created successfully")
        print()
    except Exception as e:
        print(f"✗ Error creating inventory database: {e}")
        return False

    print("=" * 60)
    print("Database initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Run the application: python app.py")
    print("2. Open browser: http://127.0.0.1:5000")
    print("3. Login with admin/admin123")
    print("4. Change admin password in Settings")
    print()

    return True

if __name__ == '__main__':
    main()
