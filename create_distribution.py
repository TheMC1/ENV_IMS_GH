#!/usr/bin/env python3
"""
Create Distribution ZIP
Creates a clean distribution package excluding development files.
"""

import os
import zipfile
from pathlib import Path

def create_distribution():
    """Create a clean distribution ZIP file"""

    # Files and folders to exclude
    exclude_patterns = {
        '.venv',
        '__pycache__',
        '.claude',
        '.idea',
        '.git',
        'archive',
        '*.db',  # Database files should be created fresh on installation
        '.pyc',
        '.pyo',
        '.pyd',
        '.so',
        '.dll',
        'create_distribution.py'  # Don't include this script
    }

    # Files to include
    include_files = [
        'app.py',
        'database.py',
        'trades_data.py',
        'requirements.txt',
        'init_databases.py',
        'setup.bat',
        'setup.sh',
        'start.bat',
        'start.sh',
        'README.md',
        'QUICK_START.md',
        'DEPLOYMENT_CHECKLIST.md',
        'CLAUDE.md',
        'VERSION',
        '.gitignore'
    ]

    # Directories to include
    include_dirs = [
        'static',
        'templates',
        'routes'
    ]

    def should_exclude(path):
        """Check if path should be excluded"""
        path_str = str(path)
        for pattern in exclude_patterns:
            if pattern in path_str:
                return True
            if path_str.endswith(pattern.replace('*', '')):
                return True
        return False

    # Create ZIP file
    zip_name = '../Carbon_IMS_v2.0_Distribution.zip'

    print("=" * 60)
    print("Creating Distribution Package")
    print("=" * 60)
    print()

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        print("Adding core files...")
        for filename in include_files:
            if os.path.exists(filename):
                arcname = f'Carbon_IMS/{filename}'
                zipf.write(filename, arcname)
                print(f"  + {filename}")

        # Add directories
        print("\nAdding directories...")
        for dir_name in include_dirs:
            if os.path.exists(dir_name):
                print(f"  Adding {dir_name}/...")
                for root, dirs, files in os.walk(dir_name):
                    # Remove excluded directories from walk
                    dirs[:] = [d for d in dirs if not should_exclude(d)]

                    for file in files:
                        if not should_exclude(file):
                            file_path = os.path.join(root, file)
                            arcname = f'Carbon_IMS/{file_path}'
                            zipf.write(file_path, arcname)
                            print(f"    + {file_path}")

    # Get file size
    size_bytes = os.path.getsize(zip_name)
    size_kb = size_bytes / 1024
    size_mb = size_kb / 1024

    print()
    print("=" * 60)
    print("Distribution Package Created Successfully!")
    print("=" * 60)
    print(f"\nFile: {os.path.abspath(zip_name)}")
    print(f"Size: {size_mb:.2f} MB ({size_kb:.2f} KB)")
    print()
    print("Package Contents:")
    print("  - Core application files (app.py, database.py)")
    print("  - Route modules (routes/)")
    print("  - All templates and static files")
    print("  - Setup and start scripts (Windows & Mac/Linux)")
    print("  - Complete documentation")
    print()
    print("Excluded from package:")
    print("  - Virtual environment (.venv)")
    print("  - Database files (*.db)")
    print("  - Python cache (__pycache__)")
    print("  - IDE settings (.idea, .claude)")
    print("  - Archive folder")
    print()
    print("Ready for distribution!")
    print()

if __name__ == '__main__':
    try:
        create_distribution()
    except Exception as e:
        print(f"Error creating distribution: {e}")
        import traceback
        traceback.print_exc()
