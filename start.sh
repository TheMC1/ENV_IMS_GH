#!/bin/bash

echo "============================================================"
echo "Carbon IMS - Inventory Management System"
echo "============================================================"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found!"
    echo "Please run ./setup.sh first."
    echo ""
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if databases exist
if [ ! -f "ims_users.db" ]; then
    echo ""
    echo "Databases not initialized!"
    echo "Running database initialization..."
    python init_databases.py
    echo ""
fi

# Start the application
echo "Starting Carbon IMS..."
echo "Application will be available at: http://127.0.0.1:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
python app.py
